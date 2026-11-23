func.func @conv(%arg0: tensor<1x32x32x8xf32>, %arg1: tensor<3x3x8x16xf32>) -> tensor<1x30x30x16xf32> {
  %0 = tosa.conv2d %arg0, %arg1, %bias, %pad, %stride, %dil : (tensor<1x32x32x8xf32>, tensor<3x3x8x16xf32>, tensor<16xf32>, tensor<4xi32>, tensor<2xi32>, tensor<2xi32>) -> tensor<1x30x30x16xf32>
  %1 = linalg.conv_2d_nhwc_hwcf ins(%arg0, %arg1 : tensor<1x32x32x8xf32>, tensor<3x3x8x16xf32>) outs(%out : tensor<1x30x30x16xf32>) -> tensor<1x30x30x16xf32>
  return %1 : tensor<1x30x30x16xf32>
}
