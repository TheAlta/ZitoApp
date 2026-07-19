param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet("init", "import-env", "set-server-password", "list", "reveal")]
    [string]$Action,

    [Parameter(Position = 1)]
    [string]$Key
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
            "env.ADMIN_SESSION_SECRET"
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
    "list" {
        $vault = Read-Vault
        @($vault.secrets.Keys) | ForEach-Object { [string]$_ } | Sort-Object
    }
    "reveal" {
        if ([string]::IsNullOrWhiteSpace($Key)) {
            throw "Usage: .\tools\zito-secrets.ps1 reveal <key>"
        }
        $vault = Read-Vault
        if (!$vault.secrets.Contains($Key)) {
            throw "Secret key not found: $Key"
        }
        $secure = $vault.secrets[$Key] | ConvertTo-SecureString
        ConvertTo-PlainText $secure
    }
}
