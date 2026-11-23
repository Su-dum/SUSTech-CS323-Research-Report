// RUN: mlir-opt %s | FileCheck %s
#map = affine_map<(d0, d1, d2) -> (d0, d2)>
#map1 = affine_map<(d0, d1, d2) -> (d2, d1)>
func.func @matmul(%A: tensor<16x32xf32>, %B: tensor<32x8xf32>) -> tensor<16x8xf32> {
  %cst = arith.constant 0.0 : f32
  %0 = tensor.empty() : tensor<16x8xf32>
  %1 = linalg.fill ins(%cst : f32) outs(%0 : tensor<16x8xf32>) -> tensor<16x8xf32>
  %2 = linalg.generic {indexing_maps = [#map, #map1, #map], iterator_types = ["parallel", "parallel", "reduction"]}
      ins(%A, %B : tensor<16x32xf32>, tensor<32x8xf32>) outs(%1 : tensor<16x8xf32>) {
    ^bb0(%a: f32, %b: f32, %c: f32):
      %d = arith.mulf %a, %b : f32
      %e = arith.addf %c, %d : f32
      linalg.yield %e : f32
  } -> tensor<16x8xf32>
  return %2 : tensor<16x8xf32>
}
