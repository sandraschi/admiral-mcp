# Per-repo fleet start config for admiral-mcp
# Edit ports/backend target here - start.ps1 is fleet-standard.
@{
    Name         = 'admiral-mcp'
    BackendPort  = 11089
    FrontendPort = 11090
    HealthPath   = '/api/v1/health'
    WebRoot      = 'webapp'
    Backend = @{
        Kind       = 'module-serve'
        Module     = 'admiral_mcp'
    }
    Frontend = @{
        Kind           = 'vite-npm'
        PackageManager = 'npm'
        PortEnvVar     = 'VITE_PORT'
        ApiTargetEnv   = 'VITE_API_TARGET'
    }
}
