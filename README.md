# MIPS CPU Simulator + nCk (Software track)

โปรเจกต์วิชา 198322 สถาปัตยกรรมคอมพิวเตอร์

**เป้าหมาย:** สร้าง CPU MIPS จำลองด้วย Python ที่รันใน command line ได้ แล้วเขียนโปรแกรม MIPS คำนวณ **factorial** และ **nCk โดยไม่ใช้คำสั่งคูณหาร** ให้ได้ถึง n = 26 ตามที่อาจารย์กำหนด (ทำได้ถึง n = 33)

โครงสร้างไฟล์ simulator แบ่งเหมือน V7.1 ของอาจารย์ (`main.py`, `cpu.py`, `isa.py`, `memory.py`) แต่เขียนใหม่ทั้งหมด และเพิ่มสิ่งที่ Readme V4–V7 ของอาจารย์แนะนำไว้ เช่น assembler แบบ 2-pass, รันจาก machine code ในหน่วยความจำ, รองรับชื่อ register และรับ input

---

## 1. วิธีรัน

ต้องมี Python 3.8 ขึ้นไป ไม่ต้องติดตั้ง library เพิ่ม

```bash
python main.py programs/nck.asm          # พิมพ์ n กับ k เช่น 5 2  -> 10
python main.py programs/factorial.asm    # พิมพ์ n เช่น 5          -> 120
```

ส่ง input ผ่าน pipe ได้ (แบบที่เครื่องตรวจอัตโนมัติใช้):

```bash
echo 26 13 | python main.py -q programs/nck.asm      # 10400600
```

| ตัวเลือก | ความหมาย |
|---|---|
| `-q` | แสดงเฉพาะผลที่โปรแกรมพิมพ์ (SYSCALL) เหมาะกับ autolab |
| `-t` | trace: แสดงทุกคำสั่งที่ทำ พร้อม address, machine code และค่าที่เปลี่ยน |
| `-s` | step: ทำทีละคำสั่ง กด Enter ไปต่อ, `d` ดู register, `r` รันจนจบ, `q` ออก |
| `-l` | แสดงตาราง address / machine code / assembly ก่อนรัน (เหมือนหน้าจอ QtSpim) |
| `-d` | แสดง register ทั้ง 32 ตัวและหน่วยความจำข้อมูลหลังรันจบ |
| `--stats` | นับจำนวนแต่ละคำสั่ง และเทียบ clock ของ single-cycle กับ multi-cycle |
| ไม่ใส่ชื่อไฟล์ | รัน `instructions.txt` (โปรแกรมตัวอย่างของอาจารย์ ได้ `$3 = 55`) |

### คำสั่งเดโมตอนนำเสนอ

```bash
python main.py programs/factorial.asm         # ใส่ 5   -> 120
python main.py programs/factorial.asm         # ใส่ 13  -> Exception: Arithmetic overflow
python main.py programs/nck.asm               # ใส่ 26 13 -> 10400600
python main.py -s programs/nck.asm            # ใส่ 3 1 แล้วกด Enter ดูทีละคำสั่ง
python main.py examples/overflow_demo.asm     # exception handler ทำงาน: พิมพ์ Cause กับ EPC
python tests/run_tests.py                     # TOTAL 633 / 633 PASS
```

---

## 2. โครงสร้างโปรเจกต์

```text
mips-sim/
├── main.py          จุดเริ่มต้น: อ่านไฟล์, สร้างเครื่อง, รัน, แสดงผล
├── cpu.py           CPU: register 32 ตัว, PC, วงจร fetch-decode-execute, SYSCALL, exception
├── isa.py           ชุดคำสั่ง: assembler (assembly -> machine code) และ decoder
├── memory.py        หน่วยความจำแบบ byte, Big Endian
├── instructions.txt โปรแกรมตัวอย่างของอาจารย์ (sum 10..1)
├── programs/
│   ├── factorial.asm   n! แบบ recursive ใช้ stack + ฟังก์ชันคูณด้วยการบวกซ้ำ
│   └── nck.asm         nCk ด้วยสามเหลี่ยมปาสคาล (บวกอย่างเดียว)
├── examples/
│   ├── sum_10_to_1.asm           โค้ดตั้งต้นของอาจารย์
│   ├── factorial_prof_format.asm factorial เขียนแบบโค้ดอาจารย์ (register เป็นเลข, ไม่มี label)
│   └── overflow_demo.asm         ทดลอง exception และ handler ที่ 0xC0000000
├── tests/
│   ├── run_tests.py    ทดสอบอัตโนมัติ เทียบกับ math.comb / math.factorial
│   └── results.txt     ผลการทดสอบล่าสุด
└── docs/
    └── อธิบายโค้ด.md    อธิบายการทำงานทีละส่วน + คำถามที่อาจารย์น่าจะถาม
```

---

## 3. Simulator ทำงานอย่างไร

1. **Assemble (isa.py)** อ่านไฟล์ assembly แล้วแปลงเป็น machine code แบบ 2-pass
   - pass 1 หาที่อยู่ของทุกคำสั่งและทุก label
   - pass 2 แปลงแต่ละคำสั่งเป็นตัวเลข 32 บิตตามรูปแบบ R / I / J
2. **Load (cpu.py)** เขียน machine code ลงหน่วยความจำ (stored program) ตั้ง `PC` = ที่อยู่เริ่มต้น และ `$sp = 0x7FFFEFFC`
3. **Run (cpu.py)** วนลูป
   - **fetch:** อ่าน word จากหน่วยความจำที่ `PC`
   - **decode:** แยกเป็น opcode / rs / rt / rd / shamt / funct / immediate
   - **execute:** ทำตามคำสั่ง อัปเดต register / memory / PC
   - จนเจอ `HALT` หรือ `SYSCALL 10`

### รูปแบบโค้ดที่รับได้ (ผสมกันในไฟล์เดียวได้)

| แบบโค้ดของอาจารย์ (V7.1) | แบบ MARS / QtSpim |
|---|---|
| `ORI $2 $0 10` | `ori $v0, $zero, 10` |
| `BNE $0 $2 -3` (นับเป็นจำนวนคำสั่ง) | `bne $v0, $zero, loop` (label) |
| `JAL 108` (ที่อยู่ byte) | `jal nck` (label) |
| `.ORG 0` และ `HALT` | comment ด้วย `#` |

### คำสั่งที่รองรับ

| กลุ่ม | คำสั่ง |
|---|---|
| R-type | `add addu sub subu and or nor slt sltu sll srl sra jr syscall` |
| I-type | `addi addiu slti sltiu andi ori lui lw sw beq bne` |
| J-type | `j jal` |
| อื่น ๆ | `mfc0` (อ่าน EPC / Cause), `halt`, `nop`, `move`, `li`, `.ORG`, `.word` |
| ไม่อนุญาต | `mul mult div divu mfhi mflo` (โจทย์ห้ามใช้คำสั่งคูณหาร) |

SYSCALL: `$v0` = 1 พิมพ์ตัวเลขใน `$a0`, 5 อ่านตัวเลขเก็บใน `$v0`, 10 จบโปรแกรม, 11 พิมพ์ตัวอักษร

`add`, `addi`, `sub` ตรวจ overflow แบบ MIPS จริง (green card หมายเหตุ 1) ถ้าผลเกิน 32 บิตจะเกิด exception: เก็บ `EPC` = ที่อยู่คำสั่งที่ผิด, `Cause` = 1 แล้วกระโดดไป `0xC0000000` (รูป 4.23 ในเอกสาร) ถ้าไม่มี handler จะหยุดและแจ้ง `Exception: Arithmetic overflow`

---

## 4. โปรแกรม MIPS

### factorial.asm
- `fact(n)` เขียนแบบ recursive: `n! = n × (n-1)!`
- เรียกตัวเองด้วย `jal` ซ้อนกัน จึงต้อง**เก็บ `$ra` และ `n` ไว้ใน stack** ก่อน แล้วอ่านคืนทีหลัง
- `mul(a, b)` คูณด้วยการบวกซ้ำ b ครั้ง (แนวคิดจาก `factorial_no_mul_1.py` ของอาจารย์)
- ได้ถูกถึง 12! = 479,001,600 ส่วน **13! = 6,227,020,800 เกิน 2,147,483,647** จึงเกิด overflow

### nck.asm
- ถ้าคิด nCk = n! / ((n-k)! k!) ตรง ๆ จะพังตั้งแต่ n = 13 เพราะ factorial ล้น 32 บิต
- จึงใช้**สามเหลี่ยมปาสคาล** `C(n,k) = C(n-1,k-1) + C(n-1,k)` เก็บแถวไว้ใน array `C[0..k]` ที่ `0x10010000`
- ใช้แค่การบวก และตัวเลขระหว่างทางไม่เคยใหญ่กว่าคำตอบ จึงได้ถึง **26C13 = 10,400,600** และไปได้ถึง 33C16 = 1,166,803,110
- รับ `0 ≤ k ≤ n ≤ 33` ถ้านอกช่วงพิมพ์ `-1`

---

## 5. ผลการทดสอบ

```text
python tests/run_tests.py

factorial 0..12        13 / 13   PASS
factorial overflow      1 / 1    PASS
factorial invalid       1 / 1    PASS
nCk n<=26             378 / 378  PASS
nCk 27..33            217 / 217  PASS
nCk invalid             5 / 5    PASS
professor format       14 / 14   PASS
exception handler       1 / 1    PASS
command line            3 / 3    PASS
----------------------------------------
TOTAL                 633 / 633  PASS
```

---

## 6. ข้อจำกัด

- ไม่มี branch delay slot (`jal` เก็บ PC+4 แทน PC+8 แบบในตำรา)
- รองรับเฉพาะคำสั่งแบบ word (`lw`, `sw`) ยังไม่มี `lb`, `sb`, `lh`, `sh`
- ยังไม่มี floating point และ `.data` segment (ใช้ `.word` หรือเขียนหน่วยความจำด้วย `sw` แทน)
- `--stats` เป็นการประมาณจำนวน clock ตามตาราง 4.22 ไม่ได้จำลอง multi-cycle จริงทีละ step
