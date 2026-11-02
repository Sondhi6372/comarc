# ============================================================
# nck.asm : อ่าน n และ k แล้วพิมพ์ nCk  (ไม่ใช้คำสั่งคูณ/หาร)
#
# ใช้สามเหลี่ยมปาสคาล:  C(n,k) = C(n-1,k-1) + C(n-1,k)
#   เก็บแถวของสามเหลี่ยมไว้ใน array C[0..k] ในหน่วยความจำ (ที่อยู่ 0x10010000)
#   เริ่มจาก C[0] = 1 แล้วทำแถว i = 1..n โดยไล่ j จากมากไปน้อย:  C[j] = C[j] + C[j-1]
#   ใช้แค่การบวก และตัวเลขระหว่างทางไม่เคยใหญ่กว่าคำตอบ จึงไม่ล้น 32 บิต
#
# รับค่า 0 <= k <= n <= 33 (ทุกคำตอบในช่วงนี้เก็บใน 32 บิตได้ สูงสุด 33C16 = 1,166,803,110)
# ถ้า input อยู่นอกช่วง พิมพ์ -1
# ============================================================
main:   addi $v0, $zero, 5        # อ่าน n
        syscall
        add  $s0, $v0, $zero      # s0 = n
        addi $v0, $zero, 5        # อ่าน k
        syscall
        add  $s1, $v0, $zero      # s1 = k
        slt  $t0, $s1, $zero      # k < 0 ?
        bne  $t0, $zero, bad
        slt  $t0, $s0, $s1        # n < k ?
        bne  $t0, $zero, bad
        slti $t0, $s0, 34         # n < 34 ?
        beq  $t0, $zero, bad
        add  $a0, $s0, $zero      # a0 = n
        add  $a1, $s1, $zero      # a1 = k
        jal  nck                  # v0 = nCk
        add  $a0, $v0, $zero
        addi $v0, $zero, 1        # พิมพ์คำตอบ
        syscall
        addi $v0, $zero, 10       # จบโปรแกรม
        syscall
bad:    addi $a0, $zero, -1       # input ผิด -> พิมพ์ -1
        addi $v0, $zero, 1
        syscall
        addi $v0, $zero, 10
        syscall

# ---------- nck(a0 = n, a1 = k) -> v0 = nCk ----------
nck:    lui  $t7, 0x1001          # t7 = ที่อยู่ของ C[0] = 0x10010000
        addi $t0, $zero, 1
        sw   $t0, 0($t7)          # C[0] = 1
        add  $t3, $a1, $zero      # ล้าง C[1..k] ให้เป็น 0
clear:  beq  $t3, $zero, rows
        sll  $t4, $t3, 2          # t4 = j * 4 (1 word = 4 byte)
        add  $t4, $t7, $t4        # t4 = ที่อยู่ของ C[j]
        sw   $zero, 0($t4)        # C[j] = 0
        addi $t3, $t3, -1
        j    clear
rows:   addi $t1, $zero, 1        # i = 1
loopi:  slt  $t2, $a0, $t1        # t2 = (n < i)
        bne  $t2, $zero, done     # ทำครบ n แถวแล้ว
        add  $t3, $t1, $zero      # j = i
        slt  $t2, $a1, $t3        # ถ้า k < j
        beq  $t2, $zero, loopj
        add  $t3, $a1, $zero      #   ให้ j = k  (ไม่ต้องคิดเกิน C[k])
loopj:  beq  $t3, $zero, nexti    # j ถึง 0 แล้ว จบแถวนี้
        sll  $t4, $t3, 2          # t4 = j * 4
        add  $t4, $t7, $t4        # t4 = ที่อยู่ของ C[j]
        lw   $t5, 0($t4)          # t5 = C[j]
        lw   $t6, -4($t4)         # t6 = C[j-1]
        add  $t5, $t5, $t6        # t5 = C[j] + C[j-1]
        sw   $t5, 0($t4)          # C[j] = t5
        addi $t3, $t3, -1         # j = j - 1
        j    loopj
nexti:  addi $t1, $t1, 1          # i = i + 1
        j    loopi
done:   sll  $t4, $a1, 2          # ที่อยู่ของ C[k]
        add  $t4, $t7, $t4
        lw   $v0, 0($t4)          # v0 = C[k] = คำตอบ
        jr   $ra
