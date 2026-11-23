func.func @ops(%a: i32, %b: i32) -> i32 {
  %0 = arith.addi %a, %b : i32
  %1 = llvm.add %0, %0 : i32
  %2 = llvm.mlir.constant(1 : i32) : i32
  return %1 : i32
}
