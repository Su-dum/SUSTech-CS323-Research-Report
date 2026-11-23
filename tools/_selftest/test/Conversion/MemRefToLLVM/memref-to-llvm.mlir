func.func @load(%m: memref<4xf32>) -> f32 {
  %0 = memref.load %m[%c0] : memref<4xf32>
  %1 = llvm.load %ptr : !llvm.ptr -> f32
  return %1 : f32
}
