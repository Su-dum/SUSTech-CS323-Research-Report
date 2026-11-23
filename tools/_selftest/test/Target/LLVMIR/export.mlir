llvm.func @foo(%a: i32) -> i32 {
  %0 = llvm.add %a, %a : i32
  llvm.return %0 : i32
}
