# memory.py
# หน่วยความจำของเครื่องจำลอง (แทน RAM)
#
# - เก็บทีละ 1 byte ใน dictionary: {address: ค่า 0-255}
#   address ที่ยังไม่เคยเขียนถือว่ามีค่า 0 (ไม่ต้องจองพื้นที่ทั้ง 4 GB)
# - ใช้แบบ Big Endian เหมือน CPU COE/MIPS-32 ในแบบฝึกหัด
#   คือ byte ที่สำคัญที่สุดอยู่ที่ address ต่ำสุด
#   เช่น เขียนค่า 0x12345678 ที่ address 0 จะได้ [0]=0x12 [1]=0x34 [2]=0x56 [3]=0x78


class MemoryError_(Exception):
    """ข้อผิดพลาดในการเข้าถึงหน่วยความจำ เช่น address ไม่หารด้วย 4 ลงตัว"""


class Memory:
    def __init__(self):
        self.data = {}

    # ---------- อ่าน/เขียนทีละ byte ----------
    def read_byte(self, address):
        return self.data.get(address & 0xFFFFFFFF, 0)

    def write_byte(self, address, value):
        self.data[address & 0xFFFFFFFF] = value & 0xFF

    # ---------- อ่าน/เขียนทีละ word (4 byte) ----------
    def check_aligned(self, address):
        if address % 4 != 0:
            raise MemoryError_("address 0x%08X is not word-aligned (must be a multiple of 4)" % (address & 0xFFFFFFFF))

    def read_word(self, address):
        """อ่าน 4 byte ต่อกันเป็นตัวเลข 32 บิต (Big Endian)"""
        self.check_aligned(address)
        value = 0
        for i in range(4):
            value = (value << 8) | self.read_byte(address + i)
        return value

    def write_word(self, address, value):
        """แยกตัวเลข 32 บิตเป็น 4 byte แล้วเขียนลงหน่วยความจำ (Big Endian)"""
        self.check_aligned(address)
        value &= 0xFFFFFFFF
        for i in range(4):
            self.write_byte(address + i, (value >> (24 - 8 * i)) & 0xFF)

    # ---------- แสดงผล ----------
    def used_words(self):
        """รายการ address (หาร 4 ลงตัว) ที่มีข้อมูลอยู่ เรียงจากน้อยไปมาก"""
        return sorted({a - a % 4 for a in self.data})

    def dump(self, start=None, count=None):
        """คืนข้อความตารางหน่วยความจำ ทีละ word: address | hex | ฐานสิบ"""
        lines = []
        addrs = self.used_words()
        if start is not None:
            addrs = [a for a in addrs if a >= start]
        if count is not None:
            addrs = addrs[:count]
        for a in addrs:
            w = self.read_word(a)
            s = w - (1 << 32) if w & 0x80000000 else w
            lines.append("  0x%08X : 0x%08X  (%d)" % (a, w, s))
        return "\n".join(lines)
