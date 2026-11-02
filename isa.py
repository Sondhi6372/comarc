# isa.py
# ISA = Instruction Set Architecture (ชุดคำสั่งของ CPU)
#
# ไฟล์นี้ทำ 2 หน้าที่
#   1) assemble()  : แปลงโปรแกรม assembly (ตัวหนังสือ) เป็น machine code (ตัวเลข 32 บิต)
#                    ใช้เทคนิค 2-pass ตามที่อาจารย์แนะนำใน Readme V4
#                    pass 1 = หาที่อยู่ของทุกบรรทัดและทุก label
#                    pass 2 = แปลงแต่ละคำสั่งเป็นตัวเลข (ตอนนี้รู้ที่อยู่ของ label ครบแล้ว)
#   2) decode()    : แยกตัวเลข 32 บิตกลับเป็นช่อง opcode, rs, rt, rd, shamt, funct, immediate
#                    CPU ใช้ตอนรัน (รันจาก machine code ในหน่วยความจำจริง ๆ แบบ stored program)
#
# รองรับโค้ด 2 รูปแบบในไฟล์เดียวกันได้
#   - แบบโค้ดของอาจารย์ (V7.1):   ORI $2 $0 10      BNE $0 $2 -3      J 108      HALT
#     (คั่นด้วยเว้นวรรค, register เป็นเลข, branch เป็นจำนวนคำสั่ง, J เป็นที่อยู่ byte)
#   - แบบ MARS / QtSpim:          loop: addi $t0, $t0, -1   # comment
#     (ใช้ label, ชื่อ register, คั่นด้วย comma, มี comment)

# ---------------- ชื่อ register ----------------
REG_NAMES = ['zero', 'at', 'v0', 'v1', 'a0', 'a1', 'a2', 'a3',
             't0', 't1', 't2', 't3', 't4', 't5', 't6', 't7',
             's0', 's1', 's2', 's3', 's4', 's5', 's6', 's7',
             't8', 't9', 'k0', 'k1', 'gp', 'sp', 'fp', 'ra']
REG_NUMBER = {}
for _i, _n in enumerate(REG_NAMES):
    REG_NUMBER['$' + _n] = _i
    REG_NUMBER['$' + str(_i)] = _i
REG_NUMBER['$s8'] = 30

# ---------------- ตารางคำสั่ง (ค่าจาก MIPS Reference Data / green card) ----------------
# R-type: opcode = 0 แยกคำสั่งด้วย funct
R_FUNCT = {'add': 0x20, 'addu': 0x21, 'sub': 0x22, 'subu': 0x23, 'and': 0x24, 'or': 0x25,
           'nor': 0x27, 'slt': 0x2A, 'sltu': 0x2B, 'sll': 0x00, 'srl': 0x02, 'sra': 0x03,
           'jr': 0x08, 'syscall': 0x0C}
# I-type: แยกด้วย opcode
I_OPCODE = {'addi': 0x08, 'addiu': 0x09, 'slti': 0x0A, 'sltiu': 0x0B, 'andi': 0x0C, 'ori': 0x0D,
            'lui': 0x0F, 'lw': 0x23, 'sw': 0x2B, 'beq': 0x04, 'bne': 0x05}
# J-type
J_OPCODE = {'j': 0x02, 'jal': 0x03}
# HALT ไม่มีใน MIPS จริง เป็นคำสั่งพิเศษของ simulator อาจารย์ ใช้ opcode 0x3F ที่ MIPS ไม่ได้ใช้
HALT_WORD = 0xFC000000
# mfc0 rt, rd : อ่าน register ของ coprocessor 0 (13 = Cause, 14 = EPC) opcode 0x10
MFC0_OPCODE = 0x10

PSEUDO = ['nop', 'move', 'li', 'halt']
FORBIDDEN = {'mul', 'mult', 'multu', 'div', 'divu', 'mfhi', 'mflo'}
ALL_MNEMONICS = set(R_FUNCT) | set(I_OPCODE) | set(J_OPCODE) | set(PSEUDO) | {'mfc0'}


class AsmError(Exception):
    """ข้อผิดพลาดตอนแปลง assembly เป็น machine code (บอกเลขบรรทัด)"""


def parse_number(text):
    """แปลงตัวเลขฐานสิบ / 0x ฐานสิบหก / 0b ฐานสอง เป็น int (ผิดรูปแบบคืน None)"""
    t = text.strip().lower()
    sign = 1
    if t.startswith('-'):
        sign, t = -1, t[1:]
    elif t.startswith('+'):
        t = t[1:]
    try:
        if t.startswith('0x'):
            return sign * int(t[2:], 16)
        if t.startswith('0b'):
            return sign * int(t[2:], 2)
        if t.isdigit():
            return sign * int(t, 10)
    except ValueError:
        pass
    return None


class Line:
    """ข้อมูลของ 1 บรรทัดในโปรแกรม"""
    def __init__(self, line_no, raw):
        self.line_no = line_no      # เลขบรรทัด (เริ่มที่ 1)
        self.raw = raw              # ข้อความเดิมทั้งบรรทัด
        self.labels = []
        self.mnemonic = None
        self.operands = []
        self.address = None
        self.size = 0               # จำนวน word ที่คำสั่งนี้ใช้ (li บางกรณีใช้ 2)
        self.words = []             # machine code ที่ได้
        self.comment = ''
        self.text = ''              # ตัวคำสั่งที่ตัด label/comment แล้ว


def split_operands(text):
    """แยก operand ได้ทั้งแบบคั่นด้วย comma และเว้นวรรค เช่น 'LW $12 4($21)' หรือ 'lw $t4, 4($s5)'"""
    text = text.replace('( ', '(').replace(' )', ')')
    parts = []
    for chunk in text.replace(',', ' ').split():
        parts.append(chunk)
    return parts


def assemble(source):
    """
    แปลงโปรแกรม assembly เป็น machine code
    คืนค่า Program ที่มี: words (dict address -> word), lines, labels, entry (ที่อยู่เริ่มรัน)
    """
    lines = []
    labels = {}
    address = 0
    entry = None

    # ===================== PASS 1: หาที่อยู่ =====================
    for no, raw in enumerate(source.replace('\r', '').split('\n'), start=1):
        L = Line(no, raw)
        text = raw
        # ตัด comment (#  ;  //)
        cut = len(text)
        for mark in ('#', ';', '//'):
            p = text.find(mark)
            if p >= 0:
                cut = min(cut, p)
        L.comment = text[cut:].lstrip('#;/ ').strip()
        text = text[:cut].strip()
        # เก็บ label (ชื่อตามด้วย :) อาจมีหลายอันในบรรทัดเดียว
        while ':' in text:
            head, rest = text.split(':', 1)
            if head.strip() and head.strip().replace('_', '').replace('.', '').isalnum() and not head.strip()[0].isdigit():
                L.labels.append(head.strip())
                text = rest.strip()
            else:
                break
        L.text = text
        for lab in L.labels:
            if lab in labels:
                raise AsmError("line %d: duplicate label '%s'" % (no, lab))
            labels[lab] = address

        if not text:
            lines.append(L)
            continue

        parts = text.split(None, 1)
        mnemonic = parts[0].lower()
        operands = split_operands(parts[1]) if len(parts) > 1 else []

        # ---- directive ----
        if mnemonic == '.org':
            value = parse_number(operands[0]) if operands else None
            if value is None:
                raise AsmError("line %d: .ORG needs a number, e.g. .ORG 0" % no)
            address = value & 0xFFFFFFFF
            for lab in L.labels:
                labels[lab] = address
            L.mnemonic = '.org'
            lines.append(L)
            continue
        if mnemonic == '.word':
            L.mnemonic = '.word'
            L.operands = operands
            L.address = address
            L.size = len(operands)
            address += 4 * L.size
            lines.append(L)
            continue
        if mnemonic in ('.text', '.globl', '.global', '.end'):
            lines.append(L)
            continue
        if mnemonic.startswith('.'):
            raise AsmError("line %d: directive '%s' is not supported" % (no, parts[0]))

        # ---- คำสั่ง ----
        if mnemonic in FORBIDDEN:
            raise AsmError("line %d: '%s' is not allowed in this project (no hardware multiply/divide)" % (no, parts[0]))
        if mnemonic not in ALL_MNEMONICS:
            raise AsmError("line %d: unknown instruction '%s'" % (no, parts[0]))
        L.mnemonic = mnemonic
        L.operands = operands
        L.address = address
        L.size = 1
        if mnemonic == 'li':
            v = parse_number(operands[1]) if len(operands) > 1 else None
            if v is None:
                raise AsmError("line %d: li needs a number" % no)
            L.size = 1 if -32768 <= v <= 32767 else 2
        if entry is None:
            entry = address
        address += 4 * L.size
        lines.append(L)

    # ===================== PASS 2: แปลงเป็นตัวเลข =====================
    words = {}
    for L in lines:
        if L.address is None or L.mnemonic is None:
            continue
        if L.mnemonic == '.word':
            for i, op in enumerate(L.operands):
                v = parse_number(op)
                if v is None:
                    v = labels.get(op)
                if v is None:
                    raise AsmError("line %d: bad .word value '%s'" % (L.line_no, op))
                L.words.append(v & 0xFFFFFFFF)
        else:
            L.words = encode(L, labels)
        for i, w in enumerate(L.words):
            words[(L.address + 4 * i) & 0xFFFFFFFF] = w

    if entry is None:
        raise AsmError("the program has no instructions")
    if 'main' in labels:
        entry = labels['main']
    return Program(lines, labels, words, entry)


class Program:
    def __init__(self, lines, labels, words, entry):
        self.lines = lines
        self.labels = labels
        self.words = words
        self.entry = entry
        # ใช้หาข้อความ assembly จาก address (สำหรับแสดงผลตอน trace)
        self.text_at = {}
        for L in lines:
            if L.address is not None and L.mnemonic and L.mnemonic != '.org':
                for i in range(L.size):
                    self.text_at[(L.address + 4 * i) & 0xFFFFFFFF] = L.text if i == 0 else L.text + '  (part 2)'

    def listing(self):
        """ตาราง address | machine code | assembly (เหมือนหน้าจอ QtSpim)"""
        out = []
        for L in self.lines:
            if L.address is None or not L.words:
                continue
            for i, w in enumerate(L.words):
                lab = (','.join(L.labels) + ':') if (i == 0 and L.labels) else ''
                out.append("  0x%08X  0x%08X  %-10s %s" % (L.address + 4 * i, w, lab, L.text if i == 0 else '(part 2)'))
        return "\n".join(out)


def reg(token, L):
    if token is None:
        raise AsmError("line %d: missing operand in '%s'" % (L.line_no, L.text))
    r = REG_NUMBER.get(token.lower())
    if r is None:
        raise AsmError("line %d: unknown register '%s'" % (L.line_no, token))
    return r


def imm16(token, L, lo=-32768, hi=65535, labels=None):
    if token is None:
        raise AsmError("line %d: missing operand in '%s'" % (L.line_no, L.text))
    v = parse_number(token)
    if v is None and labels is not None and token in labels:
        v = labels[token]
    if v is None:
        raise AsmError("line %d: bad number '%s'" % (L.line_no, token))
    if not lo <= v <= hi:
        raise AsmError("line %d: value %d does not fit in 16 bits" % (L.line_no, v))
    return v & 0xFFFF


def op_at(L, i):
    return L.operands[i] if i < len(L.operands) else None


def encode(L, labels):
    """แปลง 1 คำสั่งเป็น machine code (คืนเป็น list เพราะ li อาจได้ 2 word)"""
    m = L.mnemonic
    o = lambda i: op_at(L, i)

    if m == 'nop':
        return [0]
    if m == 'halt':
        return [HALT_WORD]
    if m == 'syscall':
        return [R_FUNCT['syscall']]
    if m == 'jr':
        return [(reg(o(0), L) << 21) | R_FUNCT['jr']]
    if m in ('sll', 'srl', 'sra'):
        sh = parse_number(o(2) or '')
        if sh is None or not 0 <= sh <= 31:
            raise AsmError("line %d: shift amount must be 0-31" % L.line_no)
        return [(reg(o(1), L) << 16) | (reg(o(0), L) << 11) | (sh << 6) | R_FUNCT[m]]
    if m in R_FUNCT:   # add rd, rs, rt
        return [(reg(o(1), L) << 21) | (reg(o(2), L) << 16) | (reg(o(0), L) << 11) | R_FUNCT[m]]
    if m == 'move':    # move rd, rs  =  addu rd, rs, $zero
        return [(reg(o(1), L) << 21) | (reg(o(0), L) << 11) | R_FUNCT['addu']]
    if m == 'li':      # li rt, value
        rt, v = reg(o(0), L), parse_number(o(1))
        if L.size == 1:
            return [(I_OPCODE['addiu'] << 26) | (rt << 16) | (v & 0xFFFF)]
        return [(I_OPCODE['lui'] << 26) | (1 << 16) | ((v >> 16) & 0xFFFF),
                (I_OPCODE['ori'] << 26) | (1 << 21) | (rt << 16) | (v & 0xFFFF)]
    if m in ('lw', 'sw'):   # lw rt, offset(rs)
        t = o(1) or ''
        if '(' not in t or not t.endswith(')'):
            raise AsmError("line %d: memory operand must look like offset($reg), e.g. 4($s1)" % L.line_no)
        off_txt, base = t[:-1].split('(', 1)
        off = imm16(off_txt or '0', L, -32768, 32767, labels)
        return [(I_OPCODE[m] << 26) | (reg(base, L) << 21) | (reg(o(0), L) << 16) | off]
    if m == 'lui':
        return [(I_OPCODE['lui'] << 26) | (reg(o(0), L) << 16) | imm16(o(1), L, 0, 65535, labels)]
    if m in ('andi', 'ori'):   # zero-extended immediate
        return [(I_OPCODE[m] << 26) | (reg(o(1), L) << 21) | (reg(o(0), L) << 16) | imm16(o(2), L, 0, 65535, labels)]
    if m in ('beq', 'bne'):
        target = o(2)
        if target is None:
            raise AsmError("line %d: branch needs a target" % L.line_no)
        off = parse_number(target)
        if off is None:   # เป็น label: คำนวณระยะห่างเป็นจำนวนคำสั่ง นับจากคำสั่งถัดไป
            if target not in labels:
                raise AsmError("line %d: label '%s' not found" % (L.line_no, target))
            off = (labels[target] - (L.address + 4)) // 4
        if not -32768 <= off <= 32767:
            raise AsmError("line %d: branch too far" % L.line_no)
        return [(I_OPCODE[m] << 26) | (reg(o(0), L) << 21) | (reg(o(1), L) << 16) | (off & 0xFFFF)]
    if m in I_OPCODE:   # addi rt, rs, imm
        hi = 65535 if m in ('addiu', 'sltiu') else 32767
        return [(I_OPCODE[m] << 26) | (reg(o(1), L) << 21) | (reg(o(0), L) << 16) | imm16(o(2), L, -32768, hi, labels)]
    if m in J_OPCODE:
        target = o(0)
        if target is None:
            raise AsmError("line %d: jump needs a target" % L.line_no)
        addr = parse_number(target)   # ตัวเลข = ที่อยู่ byte (แบบโค้ดอาจารย์)
        if addr is None:
            if target not in labels:
                raise AsmError("line %d: label '%s' not found" % (L.line_no, target))
            addr = labels[target]
        return [(J_OPCODE[m] << 26) | ((addr >> 2) & 0x3FFFFFF)]
    if m == 'mfc0':   # mfc0 rt, $13
        rd = parse_number((o(1) or '').replace('$', ''))
        if rd is None:
            raise AsmError("line %d: mfc0 needs a coprocessor register number" % L.line_no)
        return [(MFC0_OPCODE << 26) | (reg(o(0), L) << 16) | (rd << 11)]
    raise AsmError("line %d: cannot encode '%s'" % (L.line_no, L.text))


# ---------------- Decoder: ตัวเลข 32 บิต -> ช่องต่าง ๆ ----------------
FUNCT_NAME = {v: k for k, v in R_FUNCT.items()}
OPCODE_NAME = {v: k for k, v in I_OPCODE.items()}
OPCODE_NAME.update({2: 'j', 3: 'jal'})


class Decoded:
    """ผลการถอดรหัส machine code 1 คำสั่ง"""
    def __init__(self, word):
        self.word = word
        self.opcode = (word >> 26) & 0x3F   # บิต 31-26
        self.rs = (word >> 21) & 0x1F       # บิต 25-21
        self.rt = (word >> 16) & 0x1F       # บิต 20-16
        self.rd = (word >> 11) & 0x1F       # บิต 15-11
        self.shamt = (word >> 6) & 0x1F     # บิต 10-6
        self.funct = word & 0x3F            # บิต 5-0
        self.uimm = word & 0xFFFF           # immediate แบบไม่มีเครื่องหมาย
        self.imm = self.uimm - 0x10000 if self.uimm & 0x8000 else self.uimm   # sign-extend
        self.target = word & 0x3FFFFFF      # J-type address
        if word == HALT_WORD:
            self.name, self.fmt = 'halt', 'X'
        elif self.opcode == 0:
            self.name, self.fmt = FUNCT_NAME.get(self.funct), 'R'
            if word == 0:
                self.name = 'nop'
        elif self.opcode == MFC0_OPCODE and self.rs == 0:
            self.name, self.fmt = 'mfc0', 'R'
        else:
            self.name = OPCODE_NAME.get(self.opcode)
            self.fmt = 'J' if self.opcode in (2, 3) else 'I'


def decode(word):
    return Decoded(word & 0xFFFFFFFF)


def disassemble(word):
    """แปลง machine code กลับเป็นข้อความ assembly (ใช้ตอน trace)"""
    d = decode(word)
    r = lambda i: '$' + REG_NAMES[i]
    n = d.name
    if n is None:
        return '.word 0x%08X  (unknown)' % word
    if n in ('nop', 'halt', 'syscall'):
        return n
    if n == 'jr':
        return 'jr %s' % r(d.rs)
    if n in ('sll', 'srl', 'sra'):
        return '%s %s, %s, %d' % (n, r(d.rd), r(d.rt), d.shamt)
    if d.fmt == 'R' and n != 'mfc0':
        return '%s %s, %s, %s' % (n, r(d.rd), r(d.rs), r(d.rt))
    if n == 'mfc0':
        return 'mfc0 %s, $%d' % (r(d.rt), d.rd)
    if n in ('lw', 'sw'):
        return '%s %s, %d(%s)' % (n, r(d.rt), d.imm, r(d.rs))
    if n == 'lui':
        return 'lui %s, 0x%X' % (r(d.rt), d.uimm)
    if n in ('andi', 'ori'):
        return '%s %s, %s, 0x%X' % (n, r(d.rt), r(d.rs), d.uimm)
    if n in ('beq', 'bne'):
        return '%s %s, %s, %d' % (n, r(d.rs), r(d.rt), d.imm)
    if n in ('j', 'jal'):
        return '%s 0x%X' % (n, d.target << 2)
    return '%s %s, %s, %d' % (n, r(d.rt), r(d.rs), d.imm)
