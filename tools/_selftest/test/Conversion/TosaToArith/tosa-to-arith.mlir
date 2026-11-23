func.func @add(%a: tensor<4xi32>) -> tensor<4xi32> {
  %0 = tosa.add %a, %a : (tensor<4xi32>, tensor<4xi32>) -> tensor<4xi32>
  return %0 : tensor<4xi32>
}
