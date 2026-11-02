# overflow_demo.asm : ทดลอง exception (เอกสารบทที่ 4.2.1)
# addiu ไม่ตรวจ overflow แต่ addi ตรวจ -> เกิด exception แล้วกระโดดไป handler ที่ 0xC0000000
main:   lui   $t0, 0x7FFF
        ori   $t0, $t0, 0xFFFF    # t0 = 2147483647 (บวกมากที่สุดของ 32 บิต)
        addiu $t1, $t0, 1         # ไม่ตรวจ -> t1 = -2147483648
        addi  $t2, $t0, 1         # ตรวจ -> overflow exception!
        addi  $t3, $zero, 99      # คำสั่งนี้จะไม่ถูกทำ
        halt

.ORG 0xC0000000                   # exception handler
handler: mfc0 $a0, $13            # a0 = Cause (1 = overflow)
        addi  $v0, $zero, 1
        syscall
        addi  $a0, $zero, 32      # ช่องว่าง
        addi  $v0, $zero, 11
        syscall
        mfc0  $a0, $14            # a0 = EPC (ที่อยู่คำสั่งที่ผิด)
        addi  $v0, $zero, 1
        syscall
        halt
