gpu.module @kernels {
  gpu.func @add(%a: memref<128xf32>) kernel {
    %tid = gpu.thread_id x
    %0 = memref.load %a[%tid] : memref<128xf32>
    nvvm.barrier0
    gpu.return
  }
}
