# ============================================================
# factorial.asm : อ่าน n แล้วพิมพ์ n!  (ไม่ใช้คำสั่งคูณ)
#
#   - fact(n) เขียนแบบ recursive: n! = n * (n-1)!
#     เพราะเรียกตัวเองด้วย jal ซ้อนกัน จึงต้องเก็บ $ra และ n ไว้ใน stack
#   - mul(a, b) คูณด้วยการบวกซ้ำ b ครั้ง (แนวคิดจาก factorial_no_mul_1.py ของอาจารย์)
#   - n = 0..12 ได้คำตอบถูก, n = 13 ผลเกิน 32 บิต คำสั่ง add จะเกิด overflow exception
#   - n < 0 พิมพ์ -1
# ============================================================
main:   addi $v0, $zero, 5        # SYSCALL 5 = อ่านตัวเลข
        syscall                   # $v0 = n
        add  $a0, $v0, $zero      # a0 = n
        slt  $t0, $a0, $zero      # t0 = (n < 0)
        bne  $t0, $zero, bad      # n ติดลบ -> พิมพ์ -1
        jal  fact                 # v0 = fact(n)
        add  $a0, $v0, $zero      # a0 = คำตอบ
        addi $v0, $zero, 1        # SYSCALL 1 = พิมพ์ตัวเลข
        syscall
        addi $v0, $zero, 10       # SYSCALL 10 = จบโปรแกรม
        syscall
bad:    addi $a0, $zero, -1
        addi $v0, $zero, 1
        syscall
        addi $v0, $zero, 10
        syscall

# ---------- fact(a0 = n) -> v0 = n! ----------
fact:   addi $sp, $sp, -8         # จองที่ใน stack 2 word
        sw   $ra, 4($sp)          # เก็บที่อยู่กลับ (jal ข้างล่างจะเขียน $ra ทับ)
        sw   $a0, 0($sp)          # เก็บ n ไว้ใช้หลังเรียกตัวเอง
        slti $t0, $a0, 2          # t0 = (n < 2)
        beq  $t0, $zero, recur    # n >= 2 -> คำนวณต่อ
        addi $v0, $zero, 1        # กรณีฐาน: 0! = 1! = 1
        addi $sp, $sp, 8          # คืนพื้นที่ stack
        jr   $ra
recur:  addi $a0, $a0, -1         # a0 = n - 1
        jal  fact                 # v0 = (n-1)!
        lw   $a1, 0($sp)          # a1 = n (อ่านคืนจาก stack)
        add  $a0, $v0, $zero      # a0 = (n-1)!
        jal  mul                  # v0 = (n-1)! * n
        lw   $ra, 4($sp)          # คืนค่าที่อยู่กลับ
        addi $sp, $sp, 8          # คืนพื้นที่ stack
        jr   $ra

# ---------- mul(a0, a1) -> v0 = a0 * a1  (a1 >= 0) ----------
mul:    add  $v0, $zero, $zero    # v0 = 0
        add  $t1, $a1, $zero      # t1 = ตัวนับ = a1
mloop:  beq  $t1, $zero, mdone    # บวกครบแล้ว
        add  $v0, $v0, $a0        # v0 = v0 + a0  (add ตรวจ overflow)
        addi $t1, $t1, -1         # ตัวนับ - 1
        j    mloop
mdone:  jr   $ra
