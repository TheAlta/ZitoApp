param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet("init", "import-env", "set", "set-server-password", "list", "diagnose-sms", "migrate-db", "sync-mock-kb", "verify-rag", "verify-coach", "run-rag-indexer", "run-server")]
    [string]$Action,

    [Parameter(Position = 1)]
    [string]$Key,

    [ValidateRange(1, 65535)]
    [int]$Port = 8000,

    [ValidateRange(1, 1000)]
    [int]$Limit = 20,

    [ValidateRange(1, 1000)]
    [int]$ModuleNumber = 1,

    [switch]$DryRun,

    [switch]$Reload
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$SecretRoot = Join-Path $ProjectRoot ".secrets"
$VaultPath = Join-Path $SecretRoot "zito-vault.local.json"
$InventoryPath = Join-Path $SecretRoot "zito-inventory.local.json"

function Ensure-SecretRoot {
    if (!(Test-Path $SecretRoot)) {
        New-Item -ItemType Directory -Path $SecretRoot | Out-Null
    }
}

function New-EmptyVault {
    [ordered]@{
        version = 1
        warning = "Local DPAPI-encrypted vault. Do not commit. Usable only by this Windows user on this machine."
        updated_at = (Get-Date).ToString("o")
        secrets = [ordered]@{}
    }
}

function ConvertTo-Hashtable($Object) {
    $result = [ordered]@{}
    if ($null -eq $Object) { return $result }
    foreach ($property in $Object.PSObject.Properties) {
        $result[$property.Name] = $property.Value
    }
    return $result
}

function Read-Vault {
    Ensure-SecretRoot
    if (!(Test-Path $VaultPath)) {
        return New-EmptyVault
    }
    $raw = Get-Content $VaultPath -Raw -Encoding UTF8
    if ([string]::IsNullOrWhiteSpace($raw)) {
        return New-EmptyVault
    }
    $json = $raw | ConvertFrom-Json
    $vault = [ordered]@{
        version = $json.version
        warning = $json.warning
        updated_at = $json.updated_at
        secrets = ConvertTo-Hashtable $json.secrets
    }
    return $vault
}

function Save-Vault($Vault) {
    $Vault.updated_at = (Get-Date).ToString("o")
    $Vault | ConvertTo-Json -Depth 6 | Set-Content -Path $VaultPath -Encoding UTF8
}

function Set-SecretValue([string]$Name, [securestring]$SecureValue) {
    $vault = Read-Vault
    $vault.secrets[$Name] = $SecureValue | ConvertFrom-SecureString
    Save-Vault $vault
}

function ConvertFrom-PlainText([string]$Value) {
    return ConvertTo-SecureString -String $Value -AsPlainText -Force
}

function ConvertTo-PlainText([securestring]$SecureValue) {
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureValue)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
}

function Import-VaultEnvironment {
    $vault = Read-Vault
    $loaded = 0
    foreach ($name in $vault.secrets.Keys) {
        $nameText = [string]$name
        if ([string]::IsNullOrWhiteSpace($nameText) -or !$nameText.StartsWith("env.")) { continue }

        $environmentName = $nameText.Substring(4)
        if ([string]::IsNullOrWhiteSpace($environmentName)) { continue }

        $secure = $vault.secrets[$name] | ConvertTo-SecureString
        $plain = ConvertTo-PlainText $secure
        try {
            Set-Item -Path "Env:$environmentName" -Value $plain
            $loaded += 1
        }
        finally {
            $plain = $null
        }
    }
    return $loaded
}

function Get-SafeSmsDiagnostics {
    $loaded = Import-VaultEnvironment
    $urlText = [string]$env:SMSIR_API_URL
    [System.Uri]$uri = $null
    $urlIsValid = [System.Uri]::TryCreate($urlText, [System.UriKind]::Absolute, [ref]$uri)

    [ordered]@{
        vault_environment_loaded = $loaded
        otp_mock = [string]$env:OTP_MOCK
        smsir_url_configured = -not [string]::IsNullOrWhiteSpace($urlText)
        smsir_url_valid = $urlIsValid
        smsir_url_scheme = if ($urlIsValid) { $uri.Scheme } else { "" }
        smsir_url_host = if ($urlIsValid) { $uri.Host } else { "" }
        smsir_url_port = if ($urlIsValid) { $uri.Port } else { $null }
        smsir_api_key_configured = -not [string]::IsNullOrWhiteSpace([string]$env:SMSIR_API_KEY)
        smsir_template_id_configured = -not [string]::IsNullOrWhiteSpace([string]$env:SMSIR_TEMPLATE_ID)
        smsir_code_parameter_configured = -not [string]::IsNullOrWhiteSpace([string]$env:SMSIR_CODE_PARAMETER)
        smsir_timeout_seconds = [string]$env:SMSIR_TIMEOUT_SECONDS
    } | ConvertTo-Json
}

function Write-Inventory {
    Ensure-SecretRoot
    if (Test-Path $InventoryPath) { return }
    $inventory = [ordered]@{
        project = "Zito"
        domain = "https://zito.ir"
        repository = "https://github.com/TheAlta/ZitoApp"
        local_project_path = "C:\Users\ASUS\Desktop\ZitoApp"
        server = [ordered]@{
            host = "185.97.119.60"
            user = "ubuntu"
            app_path = "/opt/zito/app"
            service = "zito"
            web_server = "nginx"
        }
        deploy_commands = @(
            "cd /opt/zito/app",
            "git pull --ff-only",
            ".venv/bin/python -m compileall src",
            ".venv/bin/python -c `"from src.config import get_settings; get_settings(); print('settings-ok')`"",
            "sudo systemctl restart zito",
            "sudo systemctl is-active zito"
        )
        secret_keys = @(
            "server.ssh.password",
            "env.DATABASE_URL",
            "env.ARVAN_API_BASE_URL",
            "env.ARVAN_API_KEY",
            "env.ADMIN_PASSWORD",
            "env.ADMIN_SESSION_SECRET",
            "env.SMSIR_API_KEY",
            "env.SMSIR_TEMPLATE_ID"
        )
    }
    $inventory | ConvertTo-Json -Depth 6 | Set-Content -Path $InventoryPath -Encoding UTF8
}

switch ($Action) {
    "init" {
        Ensure-SecretRoot
        Write-Inventory
        $vault = Read-Vault
        Save-Vault $vault
        Write-Output "zito-local-password-manager-ready"
        Write-Output "inventory=$InventoryPath"
        Write-Output "vault=$VaultPath"
    }
    "import-env" {
        Ensure-SecretRoot
        $envPath = Join-Path $ProjectRoot ".env"
        if (!(Test-Path $envPath)) {
            throw ".env was not found. Create it from .env.example first."
        }
        $count = 0
        foreach ($line in Get-Content $envPath -Encoding UTF8) {
            if ($line -match '^\s*([^#][^=]+)=(.*)$') {
                $name = $matches[1].Trim()
                $value = $matches[2]
                if (![string]::IsNullOrEmpty($value)) {
                    Set-SecretValue "env.$name" (ConvertFrom-PlainText $value)
                    $count += 1
                }
            }
        }
        Write-Output "env-secrets-imported=$count"
    }
    "set-server-password" {
        Ensure-SecretRoot
        $secure = Read-Host "Enter Zito server SSH password" -AsSecureString
        Set-SecretValue "server.ssh.password" $secure
        Write-Output "server-password-saved"
    }
    "set" {
        if ([string]::IsNullOrWhiteSpace($Key)) {
            throw "Usage: .\tools\zito-secrets.ps1 set env.VARIABLE_NAME"
        }
        Ensure-SecretRoot
        $secure = Read-Host "Paste the value for $Key (input is hidden)" -AsSecureString
        Set-SecretValue $Key $secure
        Write-Output "secret-saved=$Key"
    }
    "list" {
        $vault = Read-Vault
        @($vault.secrets.Keys) | ForEach-Object { [string]$_ } | Sort-Object
    }
    "diagnose-sms" {
        Get-SafeSmsDiagnostics
    }
    "migrate-db" {
        $loaded = Import-VaultEnvironment
        $python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
        if (!(Test-Path $python)) {
            throw "Virtual environment was not found: $python"
        }

        Write-Output "vault-environment-loaded=$loaded"
        & $python -m alembic upgrade head
        exit $LASTEXITCODE
    }
    "sync-mock-kb" {
        $loaded = Import-VaultEnvironment
        $python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
        if (!(Test-Path $python)) {
            throw "Virtual environment was not found: $python"
        }

        $arguments = @("-m", "src.cli.kb_sync")
        if ($DryRun) { $arguments += "--dry-run" }
        Write-Output "vault-environment-loaded=$loaded"
        & $python @arguments
        exit $LASTEXITCODE
    }
    "verify-rag" {
        $loaded = Import-VaultEnvironment
        $python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
        if (!(Test-Path $python)) {
            throw "Virtual environment was not found: $python"
        }

        Write-Output "vault-environment-loaded=$loaded"
        & $python -m src.cli.rag_verify --module-number $ModuleNumber
        exit $LASTEXITCODE
    }
    "verify-coach" {
        $loaded = Import-VaultEnvironment
        $python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
        if (!(Test-Path $python)) {
            throw "Virtual environment was not found: $python"
        }

        Write-Output "vault-environment-loaded=$loaded"
        & $python -m src.cli.coach_verify --module-number $ModuleNumber
        exit $LASTEXITCODE
    }
    "run-rag-indexer" {
        $loaded = Import-VaultEnvironment
        $python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
        if (!(Test-Path $python)) {
            throw "Virtual environment was not found: $python"
        }

        Write-Output "vault-environment-loaded=$loaded"
        & $python -m src.cli.rag_indexer --once --limit $Limit
        exit $LASTEXITCODE
    }
    "run-server" {
        $loaded = Import-VaultEnvironment
        $python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
        if (!(Test-Path $python)) {
            throw "Virtual environment was not found: $python"
        }

        $arguments = @("-m", "uvicorn", "src.main:app", "--host", "127.0.0.1", "--port", $Port.ToString())
        if ($Reload) { $arguments += "--reload" }
        Write-Output "vault-environment-loaded=$loaded"
        & $python @arguments
        exit $LASTEXITCODE
    }
}
