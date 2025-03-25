# MCP Java SDK

This directory contains the Java SDK for the Model Context Protocol (MCP).

## Installation

Add the following dependency to your `pom.xml`:

```xml
<dependency>
    <groupId>com.mcp</groupId>
    <artifactId>java-sdk</artifactId>
    <version>1.0.0</version>
</dependency>
```

## Usage

```java
import com.mcp.sdk.MCPClient;

// Example usage
MCPClient client = new MCPClient();
client.connect();
```
