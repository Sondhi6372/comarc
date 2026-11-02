# cpu.py
# CPU จำลองแบบ MIPS 32 บิต
#
# ส่วนประกอบ
#   - registers[0..31]  register 32 ช่อง เก็บแบบ unsigned 32 บิต (0 .. 0xFFFFFFFF)
#   - PC                ที่อยู่ของคำสั่งถัดไป (ที่อยู่ byte จริง เพิ่มทีละ 4)
#   - memory            หน่วยความจำ (memory.py) เก็บทั้งคำสั่งและข้อมูล = stored program
#   - EPC, Cause        register ของ coprocessor 0 ใช้ตอนเกิด exception (เอกสารบทที่ 4.2.1)
#
# วงจรการทำงาน (instruction cycle)
#   1. fetch   : อ่าน machine code 32 บิตจาก memory ที่ address = PC
#   2. decode  : แยกเป็นช่อง opcode / rs / rt / rd / shamt / funct / immediate (isa.decode)
#   3. execute : ทำงานตามคำสั่ง แล้วอัปเดต register / memory / PC
#   วนจนเจอ HALT หรือ SYSCALL 10

from isa import decode, disassemble, REG_NAMES
from memory import MemoryError_

MASK32 = 0xFFFFFFFF
SP_INIT = 0x7FFFEFFC          # ค่าเริ่มต้นของ $sp เหมือน QtSpim / MARS
EXCEPTION_VECTOR = 0xC0000000  # ที่อยู่ของ exception handler (รูป 4.23 ในเอกสาร)

# จำนวน clock ต่อคำสั่งใน multi-cycle machine (ตาราง 4.22) ใช้สำหรับ --stats
MULTICYCLE_CLOCKS = {'lw': 5, 'sw': 4, 'beq': 3, 'bne': 3, 'j': 3, 'jal': 3, 'jr': 3}


def to_signed(v):
    """แปลงเลข 32 บิตแบบ unsigned เป็นแบบมีเครื่องหมาย (two's complement)"""
    v &= MASK32
    return v - (1 << 32) if v & 0x80000000 else v


class CPUException(Exception):
    """exception ของ CPU ที่ไม่มี handler รองรับ ทำให้โปรแกรมหยุด"""
    def __init__(self, kind, pc, message):
        super().__init__(message)
        self.kind = kind
        self.pc = pc


class CPU:
    def __init__(self, program, memory, read_int=None, write=None):
        """
        program  : ผลจาก isa.assemble()
        memory   : Memory()
        read_int : ฟังก์ชันอ่านตัวเลขสำหรับ SYSCALL 5
        write    : ฟังก์ชันพิมพ์ข้อความสำหรับ SYSCALL 1 / 11
        """
        self.program = program
        self.memory = memory
        self.registers = [0] * 32
        self.registers[29] = SP_INIT
        self.PC = program.entry
        self.EPC = 0
        self.Cause = 0
        self.running = True
        self.steps = 0                 # จำนวนคำสั่งที่ทำไปแล้ว
        self.stop_reason = ''
        self.read_int = read_int or (lambda: 0)
        self.write = write or (lambda s: None)
        self.mix = {}                  # นับว่าแต่ละคำสั่งถูกใช้กี่ครั้ง (สำหรับ --stats)
        self.last_changes = []         # สิ่งที่เปลี่ยนในคำสั่งล่าสุด (สำหรับ --trace)
        # โหลดโปรแกรม (machine code) ลงหน่วยความจำ = stored program
        for address, word in program.words.items():
            memory.write_word(address, word)

    # ---------------- ช่วยอ่าน/เขียน register ----------------
    def set_reg(self, r, value):
        """เขียน register (ห้ามเขียน $zero เพราะต้องเป็น 0 เสมอ)"""
        if r == 0:
            return
        value &= MASK32
        if self.registers[r] != value:
            self.last_changes.append('$%s = %d' % (REG_NAMES[r], to_signed(value)))
        self.registers[r] = value

    def get(self, r):
        return self.registers[r]

    # ---------------- exception ----------------
    def raise_exception(self, kind, pc):
        """
        จัดการ exception ตามเอกสารบทที่ 4.2.1
          1) EPC = ที่อยู่ของคำสั่งที่ทำให้เกิด exception
          2) Cause = เหตุ (0 = undefined instruction, 1 = arithmetic overflow)
          3) PC = ที่อยู่ของ exception handler (0xC0000000)
        ถ้าโปรแกรมไม่มี handler ที่ 0xC0000000 จะหยุดและแจ้งข้อผิดพลาด
        """
        self.EPC = pc
        self.Cause = 1 if kind == 'overflow' else 0
        what = 'Arithmetic overflow' if kind == 'overflow' else 'Undefined instruction'
        self.last_changes.append('EXCEPTION %s: EPC = 0x%08X, Cause = %d' % (what, pc, self.Cause))
        if EXCEPTION_VECTOR in self.program.words:
            self.PC = EXCEPTION_VECTOR
            return
        raise CPUException(kind, pc, '%s at PC = 0x%08X  (%s)' % (what, pc, self.program.text_at.get(pc, '?')))

    # ---------------- 1 คำสั่ง ----------------
    def step(self):
        self.last_changes = []
        pc = self.PC
        if pc not in self.program.text_at:
            self.running = False
            self.stop_reason = 'PC = 0x%08X has no instruction (ran past the end of the program)' % pc
            return None
        # 1) FETCH
        word = self.memory.read_word(pc)
        # 2) DECODE
        d = decode(word)
        # 3) EXECUTE
        self.PC = (pc + 4) & MASK32          # ปกติไปคำสั่งถัดไป (branch/jump จะเขียนทับ)
        self.steps += 1
        self.mix[d.name or '???'] = self.mix.get(d.name or '???', 0) + 1
        self.execute(d, pc)
        return d

    def execute(self, d, pc):
        n = d.name
        rs, rt = self.get(d.rs), self.get(d.rt)
        s_rs, s_rt = to_signed(rs), to_signed(rt)

        if n is None:
            self.raise_exception('undefined', pc)

        # ---------- R-type: rd = rs op rt ----------
        elif n == 'add':          # บวกแบบตรวจ overflow
            r = s_rs + s_rt
            if r > 0x7FFFFFFF or r < -0x80000000:
                self.raise_exception('overflow', pc)
            else:
                self.set_reg(d.rd, r)
        elif n == 'addu':         # บวกแบบไม่ตรวจ overflow
            self.set_reg(d.rd, rs + rt)
        elif n == 'sub':
            r = s_rs - s_rt
            if r > 0x7FFFFFFF or r < -0x80000000:
                self.raise_exception('overflow', pc)
            else:
                self.set_reg(d.rd, r)
        elif n == 'subu':
            self.set_reg(d.rd, rs - rt)
        elif n == 'and':
            self.set_reg(d.rd, rs & rt)
        elif n == 'or':
            self.set_reg(d.rd, rs | rt)
        elif n == 'nor':
            self.set_reg(d.rd, ~(rs | rt))
        elif n == 'slt':          # เปรียบเทียบแบบมีเครื่องหมาย
            self.set_reg(d.rd, 1 if s_rs < s_rt else 0)
        elif n == 'sltu':         # เปรียบเทียบแบบไม่มีเครื่องหมาย
            self.set_reg(d.rd, 1 if rs < rt else 0)
        elif n == 'sll':
            self.set_reg(d.rd, rt << d.shamt)
        elif n == 'srl':
            self.set_reg(d.rd, rt >> d.shamt)
        elif n == 'sra':
            self.set_reg(d.rd, s_rt >> d.shamt)
        elif n == 'nop':
            pass
        elif n == 'jr':
            self.PC = rs
        elif n == 'syscall':
            self.syscall()

        # ---------- I-type: rt = rs op immediate ----------
        elif n == 'addi':
            r = s_rs + d.imm
            if r > 0x7FFFFFFF or r < -0x80000000:
                self.raise_exception('overflow', pc)
            else:
                self.set_reg(d.rt, r)
        elif n == 'addiu':
            self.set_reg(d.rt, rs + d.imm)
        elif n == 'slti':
            self.set_reg(d.rt, 1 if s_rs < d.imm else 0)
        elif n == 'sltiu':
            self.set_reg(d.rt, 1 if rs < (d.imm & MASK32) else 0)
        elif n == 'andi':         # immediate แบบเติม 0 ด้านหน้า (zero-extend)
            self.set_reg(d.rt, rs & d.uimm)
        elif n == 'ori':
            self.set_reg(d.rt, rs | d.uimm)
        elif n == 'lui':          # เอาค่าไปไว้ 16 บิตบน
            self.set_reg(d.rt, d.uimm << 16)
        elif n == 'lw':           # rt = Memory[rs + offset]
            address = (rs + d.imm) & MASK32
            self.set_reg(d.rt, self.memory.read_word(address))
        elif n == 'sw':           # Memory[rs + offset] = rt
            address = (rs + d.imm) & MASK32
            self.memory.write_word(address, rt)
            self.last_changes.append('Mem[0x%08X] = %d' % (address, s_rt))
        elif n == 'beq':          # ถ้าเท่ากัน กระโดดไป PC + 4 + offset*4
            if rs == rt:
                self.PC = (pc + 4 + d.imm * 4) & MASK32
        elif n == 'bne':
            if rs != rt:
                self.PC = (pc + 4 + d.imm * 4) & MASK32

        # ---------- J-type ----------
        elif n in ('j', 'jal'):
            target = ((pc + 4) & 0xF0000000) | (d.target << 2)
            if n == 'jal':
                self.set_reg(31, pc + 4)    # $ra = ที่อยู่กลับ
            if n == 'j' and target == pc:   # j กระโดดอยู่กับที่ = จบโปรแกรม
                self.running = False
                self.stop_reason = 'j to itself (program end)'
            self.PC = target

        # ---------- พิเศษ ----------
        elif n == 'mfc0':
            value = self.EPC if d.rd == 14 else self.Cause if d.rd == 13 else 0
            self.set_reg(d.rt, value)
        elif n == 'halt':
            self.running = False
            self.stop_reason = 'HALT'

    # ---------------- SYSCALL ----------------
    def syscall(self):
        """
        บริการของระบบ เลือกด้วยค่าใน $v0 ($2) เหมือน QtSpim / MARS
          1  : พิมพ์ตัวเลขใน $a0
          5  : อ่านตัวเลขจากคีย์บอร์ดเก็บใน $v0
          10 : จบโปรแกรม
          11 : พิมพ์ตัวอักษรตามรหัสใน $a0
        """
        service = to_signed(self.registers[2])
        a0 = self.registers[4]
        if service == 1:
            self.write(str(to_signed(a0)))
        elif service == 11:
            self.write(chr(a0 & 0xFF))
        elif service == 5:
            self.set_reg(2, self.read_int())
        elif service == 10:
            self.running = False
            self.stop_reason = 'SYSCALL 10 (exit)'
        else:
            raise CPUException('syscall', self.PC - 4, 'SYSCALL %d is not supported (use 1, 5, 10, 11)' % service)

    # ---------------- รันจนจบ ----------------
    def run(self, max_steps=10_000_000, on_step=None):
        """รันจนกว่าจะเจอ HALT / SYSCALL 10 (on_step ถูกเรียกหลังทุกคำสั่ง ใช้กับ --trace)"""
        while self.running:
            if self.steps >= max_steps:
                self.running = False
                self.stop_reason = 'stopped after %d steps (infinite loop?)' % max_steps
                break
            pc = self.PC
            d = self.step()
            if d is not None and on_step:
                on_step(self, pc, d)

    # ---------------- สถิติ ----------------
    def cycle_stats(self):
        """เทียบจำนวน clock ถ้ารันบน single-cycle กับ multi-cycle (ตาราง 4.22)"""
        single = self.steps
        multi = 0
        for name, count in self.mix.items():
            multi += MULTICYCLE_CLOCKS.get(name, 4) * count
        return single, multi
