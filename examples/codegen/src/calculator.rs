use mcp_codegen::tool;
use mcp_kit::handler::{ToolError, ToolHandler};

#[tokio::main]
async fn main() -> std::result::Result<(), Box<dyn std::error::Error>> {
    // Create an instance of our tool
    let calculator = Calculator;

    // Print tool information
    println!("Tool name: {}", calculator.name());
    println!("Tool description: {}", calculator.description());
    println!("Tool schema: {}", calculator.schema());

    // Test the tool with some sample input
    let input = serde_json::json!({
        "x": 5,
        "y": 3,
        "operation": "multiply"
    });

    match calculator.call(input).await {
        Ok(result) => println!("Result: {}", result),
        Err(e) => println!("Error calling calculator: {}", e),
    }

    Ok(())
}

#[tool(
    name = "calculator",
    description = "Perform basic arithmetic operations",
    params(
        x = "First number in the calculation",
        y = "Second number in the calculation",
        operation = "The operation to perform (add, subtract, multiply, divide)"
    )
)]
async fn calculator(x: i32, y: i32, operation: String) -> Result<i32, ToolError> {
    match operation.as_str() {
        "add" => Ok(x + y),
        "subtract" => Ok(x - y),
        "multiply" => Ok(x * y),
        "divide" => {
            if y == 0 {
                Err(ToolError::ExecutionError("Division by zero".into()))
            } else {
                Ok(x / y)
            }
        }
        _ => Err(ToolError::InvalidParameters(format!(
            "Unknown operation: {}",
            operation
        ))),
    }
}
