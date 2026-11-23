func.func @loop(%lb: index, %ub: index, %step: index) {
  scf.for %iv = %lb to %ub step %step {
    %c = arith.constant 1 : i32
    memref.store %c, %m[%iv] : memref<?xi32>
  }
  return
}
