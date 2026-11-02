# main.py
# จุดเริ่มต้นของโปรแกรม (ปุ่มเปิดเครื่อง)
#
# วิธีใช้:
#   python main.py programs/nck.asm              รันแล้วแสดงผลลัพธ์ + สรุป
#   python main.py -q programs/nck.asm           แสดงเฉพาะผลจาก SYSCALL (สำหรับตรวจอัตโนมัติ / autolab)
#   python main.py -t programs/factorial.asm     trace: แสดงทุกคำสั่งที่ทำและค่าที่เปลี่ยน
#   python main.py -s programs/factorial.asm     step: ทำทีละคำสั่ง กด Enter เพื่อไปต่อ
#   python main.py -l programs/nck.asm           แสดงตาราง address / machine code ก่อนรัน
#   python main.py -d programs/nck.asm           แสดง register และ memory หลังรันจบ
#   python main.py --stats programs/nck.asm      สถิติคำสั่ง + เทียบ single-cycle กับ multi-cycle
#   python main.py                               ไม่ใส่ชื่อไฟล์ = รัน instructions.txt (เหมือน V7.1)
#
# input ของ SYSCALL 5 พิมพ์ได้ทั้งบรรทัดเดียว (5 2) หรือทีละบรรทัด หรือส่งผ่าน pipe:
#   echo 5 2 | python main.py -q programs/nck.asm

import argparse
import sys

from isa import assemble, AsmError, REG_NAMES
from memory import Memory, MemoryError_
from cpu import CPU, CPUException, to_signed


class InputReader:
    """อ่านตัวเลขทีละตัวจาก stdin สำหรับ SYSCALL 5 (รองรับหลายตัวในบรรทัดเดียว)"""
    def __init__(self, interactive):
        self.buffer = []
        self.interactive = interactive

    def __call__(self):
        while not self.buffer:
            if self.interactive:
                sys.stderr.write('input> ')
                sys.stderr.flush()
            line = sys.stdin.readline()
            if line == '':                       # ไม่มี input เหลือแล้ว
                raise CPUException('input', 0, 'SYSCALL 5: no more input (expected an integer)')
            self.buffer = line.split()
        token = self.buffer.pop(0)
        try:
            return int(token, 0)
        except ValueError:
            raise CPUException('input', 0, "SYSCALL 5: '%s' is not an integer" % token)


def print_registers(cpu):
    print('Registers:')
    for i in range(0, 32, 4):
        cells = []
        for r in range(i, i + 4):
            cells.append('$%-2d %-4s = 0x%08X' % (r, '$' + REG_NAMES[r], cpu.registers[r]))
        print('  ' + '   '.join(cells))
    print('  PC = 0x%08X   EPC = 0x%08X   Cause = %d' % (cpu.PC, cpu.EPC, cpu.Cause))


def main(argv=None):
    ap = argparse.ArgumentParser(description='MIPS CPU simulator (Python)')
    ap.add_argument('file', nargs='?', default='instructions.txt', help='assembly file (.asm / .txt)')
    ap.add_argument('-q', '--quiet', action='store_true', help='print only SYSCALL output')
    ap.add_argument('-t', '--trace', action='store_true', help='print every executed instruction')
    ap.add_argument('-s', '--step', action='store_true', help='run one instruction per Enter key')
    ap.add_argument('-l', '--listing', action='store_true', help='print address / machine code listing')
    ap.add_argument('-d', '--dump', action='store_true', help='print registers and memory at the end')
    ap.add_argument('--stats', action='store_true', help='instruction mix and cycle comparison')
    ap.add_argument('--max-steps', type=int, default=10_000_000, help='stop after this many instructions')
    args = ap.parse_args(argv)

    # ---------- โหลดและแปลงโปรแกรม ----------
    try:
        with open(args.file, 'r', encoding='utf-8', errors='replace') as f:
            source = f.read()
    except OSError as e:
        print('Cannot open file: %s' % e, file=sys.stderr)
        return 1
    try:
        program = assemble(source)
    except AsmError as e:
        print('Assembly error: %s' % e, file=sys.stderr)
        return 1

    if args.listing and not args.quiet:
        print('Program listing (address, machine code, instruction):')
        print(program.listing())
        print()

    # ---------- สร้างเครื่อง ----------
    out_parts = []

    def write(text):
        out_parts.append(text)
        sys.stdout.write(text)
        sys.stdout.flush()

    interactive = sys.stdin.isatty() and not args.quiet
    memory = Memory()
    cpu = CPU(program, memory, read_int=InputReader(interactive), write=write)

    # ---------- trace / step ----------
    state = {'step_mode': args.step}

    def on_step(c, pc, d):
        changes = ', '.join(c.last_changes)
        if pc != (c.PC - 4) & 0xFFFFFFFF:
            changes = (changes + ', ' if changes else '') + 'PC -> 0x%08X' % c.PC
        line = '[%6d] 0x%08X  0x%08X  %-26s %s' % (c.steps, pc, d.word, c.program.text_at.get(pc, ''), changes)
        if out_parts and not out_parts[-1].endswith('\n'):
            sys.stdout.write('\n')
            out_parts.append('\n')
        print(line)
        if state['step_mode'] and c.running:
            try:
                cmd = input('  [Enter] next   [r] run to end   [d] registers   [q] quit > ').strip().lower()
            except EOFError:
                cmd = 'r'
            if cmd == 'd':
                print_registers(c)
            elif cmd == 'r':
                state['step_mode'] = False
            elif cmd == 'q':
                c.running = False
                c.stop_reason = 'stopped by user'

    trace = (args.trace or args.step) and not args.quiet
    error = None
    try:
        cpu.run(max_steps=args.max_steps, on_step=on_step if trace else None)
    except CPUException as e:
        error = e
    except MemoryError_ as e:
        error = CPUException('memory', cpu.PC, 'Memory error: %s' % e)

    if out_parts and not out_parts[-1].endswith('\n'):
        sys.stdout.write('\n')

    # ---------- สรุปผล ----------
    if error is not None:
        print('Exception: %s' % error, file=sys.stderr)
        if not args.quiet:
            print('  EPC = 0x%08X, Cause = %d   (Cause 1 = overflow, 0 = undefined instruction)' % (cpu.EPC, cpu.Cause))
            print('Steps: %d' % cpu.steps)
            if args.dump:
                print_registers(cpu)
        return 2

    if not args.quiet:
        if out_parts:
            print('Output: %s' % ''.join(out_parts).strip())
        nonzero = ['$%d($%s)=%d' % (r, REG_NAMES[r], to_signed(cpu.registers[r]))
                   for r in range(1, 32) if cpu.registers[r] != 0 and r not in (29, 31)]
        print('Registers != 0: %s' % (', '.join(nonzero) if nonzero else '(none)'))
        print('Steps: %d   [%s]' % (cpu.steps, cpu.stop_reason))
        if args.stats:
            single, multi = cpu.cycle_stats()
            print('Instruction mix:')
            for name, count in sorted(cpu.mix.items(), key=lambda kv: -kv[1]):
                print('  %-8s %8d' % (name, count))
            print('Clock cycles if run on:')
            print('  single-cycle : %d cycles (CPI 1.00, long clock)' % single)
            print('  multi-cycle  : %d cycles (CPI %.2f, short clock)' % (multi, multi / max(1, single)))
        if args.dump:
            print_registers(cpu)
            print('Memory (data, words that are not program code):')
            code = set(program.words)
            data = [a for a in memory.used_words() if a not in code]
            for a in data[:64]:
                w = memory.read_word(a)
                print('  0x%08X : 0x%08X  (%d)' % (a, w, to_signed(w)))
            if not data:
                print('  (none)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
