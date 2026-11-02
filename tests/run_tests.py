# tests/run_tests.py
# ทดสอบอัตโนมัติ: รันโปรแกรม MIPS บน simulator แล้วเทียบกับคำตอบที่ Python คำนวณ
#
# วิธีรัน (จากโฟลเดอร์หลักของโปรเจกต์):
#   python tests/run_tests.py
#
# ส่วนที่ 1-4 เรียก simulator ตรง ๆ (เร็ว) ส่วนที่ 5 เรียกผ่าน command line จริง
# (แบบที่ autolab จะใช้) ผลสรุปถูกบันทึกใน tests/results.txt

import math
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from isa import assemble          # noqa: E402
from memory import Memory         # noqa: E402
from cpu import CPU, CPUException  # noqa: E402


def run(path, inputs):
    """รันไฟล์ .asm ด้วย input ที่กำหนด คืน (ข้อความที่พิมพ์ออกมา, exception หรือ None, cpu)"""
    with open(os.path.join(ROOT, path), encoding='utf-8') as f:
        program = assemble(f.read())
    queue = list(inputs)
    out = []
    cpu = CPU(program, Memory(), read_int=lambda: queue.pop(0), write=out.append)
    try:
        cpu.run(max_steps=5_000_000)
        return ''.join(out), None, cpu
    except CPUException as e:
        return ''.join(out), e, cpu


results = []
failures = []


def check(group, name, ok, detail=''):
    results.append((group, ok))
    if not ok:
        failures.append('%s: %s %s' % (group, name, detail))


# ---------- 1) factorial: 0..12 ต้องถูก ----------
for n in range(0, 13):
    out, err, _ = run('programs/factorial.asm', [n])
    check('factorial 0..12', 'n=%d' % n, err is None and out == str(math.factorial(n)), '(got %r, %s)' % (out, err))
# 13 ต้องเกิด overflow exception (13! = 6,227,020,800 เกิน 2,147,483,647)
out, err, _ = run('programs/factorial.asm', [13])
check('factorial overflow', 'n=13', err is not None and err.kind == 'overflow', '(got %r, %s)' % (out, err))
out, err, _ = run('programs/factorial.asm', [-3])
check('factorial invalid', 'n=-3', out == '-1')

# ---------- 2) nCk: ทุกคู่ 0 <= k <= n <= 33 ----------
max_steps = 0
for n in range(0, 34):
    for k in range(0, n + 1):
        out, err, cpu = run('programs/nck.asm', [n, k])
        max_steps = max(max_steps, cpu.steps)
        group = 'nCk n<=26' if n <= 26 else 'nCk 27..33'
        check(group, 'C(%d,%d)' % (n, k), err is None and out == str(math.comb(n, k)), '(got %r, %s)' % (out, err))

# ---------- 3) nCk: input ผิด ต้องพิมพ์ -1 ----------
for n, k in [(5, 6), (5, -1), (-1, 0), (34, 17), (40, 2)]:
    out, err, _ = run('programs/nck.asm', [n, k])
    check('nCk invalid', 'C(%d,%d)' % (n, k), err is None and out == '-1', '(got %r)' % out)

# ---------- 4) ตัวอย่างรูปแบบโค้ดของอาจารย์ ----------
out, err, cpu = run('instructions.txt', [])
check('professor format', 'instructions.txt ($3 = 55)', err is None and cpu.registers[3] == 55)
for n in range(0, 13):
    out, err, _ = run('examples/factorial_prof_format.asm', [n])
    check('professor format', 'factorial n=%d' % n, err is None and out == str(math.factorial(max(n, 1)) if n > 0 else '1'))
out, err, cpu = run('examples/overflow_demo.asm', [])
check('exception handler', 'overflow_demo', err is None and out == '1 12' and cpu.EPC == 12 and cpu.Cause == 1, '(got %r)' % out)

# ---------- 5) เรียกผ่าน command line จริง ----------
for args, stdin, expect in [(['-q', 'programs/nck.asm'], '5 2\n', '10'),
                            (['-q', 'programs/nck.asm'], '26\n13\n', '10400600'),
                            (['-q', 'programs/factorial.asm'], '5\n', '120')]:
    p = subprocess.run([sys.executable, 'main.py'] + args, input=stdin, capture_output=True, text=True, cwd=ROOT, timeout=30)
    check('command line', ' '.join(args) + ' < ' + stdin.strip(), p.stdout.strip() == expect, '(got %r)' % p.stdout)

# ---------- สรุป ----------
groups = []
for g, _ in results:
    if g not in groups:
        groups.append(g)
lines = []
for g in groups:
    total = sum(1 for x, _ in results if x == g)
    passed = sum(1 for x, ok in results if x == g and ok)
    lines.append('%-20s %4d / %-4d %s' % (g, passed, total, 'PASS' if passed == total else 'FAIL'))
total = len(results)
passed = sum(1 for _, ok in results if ok)
lines.append('-' * 40)
lines.append('%-20s %4d / %-4d %s' % ('TOTAL', passed, total, 'PASS' if passed == total else 'FAIL'))
lines.append('(longest nCk run: %d instructions)' % max_steps)
if failures:
    lines.append('')
    lines.append('Failures:')
    lines.extend('  ' + f for f in failures)
report = '\n'.join(lines)
print(report)
with open(os.path.join(ROOT, 'tests', 'results.txt'), 'w', encoding='utf-8') as f:
    f.write(report + '\n')
sys.exit(0 if not failures else 1)
