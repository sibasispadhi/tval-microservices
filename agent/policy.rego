package tval

default allow = false

allow {
  input.target == "payments"
  input.param == "MAX_CONCURRENCY"
  input.proposed >= 4
  input.proposed <= 64
}
