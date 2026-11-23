func.func @f(%a: i32) -> i32 {
  %0 = arith.addi %a, %c0 : i32
  return %0 : i32
}
