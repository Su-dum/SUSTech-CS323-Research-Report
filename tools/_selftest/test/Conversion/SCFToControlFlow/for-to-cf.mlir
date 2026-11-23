func.func @loop(%lb: index, %ub: index, %step: index) {
  scf.for %iv = %lb to %ub step %step {
    cf.br ^bb1
  ^bb1:
    cf.br ^bb2
  ^bb2:
    return
  }
}
