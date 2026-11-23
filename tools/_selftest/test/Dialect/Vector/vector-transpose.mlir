func.func @transpose(%v: vector<4x8xf32>) -> vector<8x4xf32> {
  %0 = vector.transpose %v, [1, 0] : vector<4x8xf32> to vector<8x4xf32>
  %1 = vector.bitcast %0 : vector<8x4xf32> to vector<32xf32>
  %2 = arith.addf %1, %1 : vector<32xf32>
  return %2 : vector<32xf32>
}
