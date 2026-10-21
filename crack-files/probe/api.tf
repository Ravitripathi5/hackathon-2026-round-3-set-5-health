resource "aws_lambda_function_url" "probe" {
  function_name      = "health-probe"
  authorization_type = "NONE"

  cors {
    allow_origins     = ["*"]
    allow_credentials = true
  }
}
