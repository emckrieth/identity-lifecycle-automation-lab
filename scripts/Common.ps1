Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$script:RepoRoot = Split-Path -Parent $PSScriptRoot
$script:DataPath = Join-Path $script:RepoRoot "data"
$script:OutputPath = Join-Path $script:RepoRoot "output"
$script:UsersPath = Join-Path $script:DataPath "users.json"
$script:RoleMapPath = Join-Path $script:DataPath "role_map.json"
$script:AuditLogPath = Join-Path $script:OutputPath "audit-log.csv"
$script:AccessReviewPath = Join-Path $script:OutputPath "access-review-report.csv"

function Initialize-LabOutput {
    if (-not (Test-Path $script:OutputPath)) {
        New-Item -ItemType Directory -Path $script:OutputPath | Out-Null
    }

    if (-not (Test-Path $script:AuditLogPath)) {
        "Timestamp,TicketId,Workflow,UserPrincipalName,Action,Result,Details" | Out-File -FilePath $script:AuditLogPath -Encoding utf8
    }
}

function Get-LabUsers {
    if (-not (Test-Path $script:UsersPath)) {
        return @()
    }

    $users = Get-Content -Raw -Path $script:UsersPath | ConvertFrom-Json
    if ($null -eq $users) {
        return @()
    }

    return @($users)
}

function Save-LabUsers {
    param(
        [Parameter(Mandatory = $true)]
        [array]$Users
    )

    $Users | ConvertTo-Json -Depth 10 | Out-File -FilePath $script:UsersPath -Encoding utf8
}

function Get-RoleMap {
    Get-Content -Raw -Path $script:RoleMapPath | ConvertFrom-Json
}

function Write-AuditEntry {
    param(
        [Parameter(Mandatory = $true)][string]$TicketId,
        [Parameter(Mandatory = $true)][string]$Workflow,
        [Parameter(Mandatory = $true)][string]$UserPrincipalName,
        [Parameter(Mandatory = $true)][string]$Action,
        [Parameter(Mandatory = $true)][string]$Result,
        [Parameter(Mandatory = $true)][string]$Details
    )

    Initialize-LabOutput
    $timestamp = (Get-Date).ToUniversalTime().ToString("s") + "Z"
    $safeDetails = $Details.Replace('"', '""')
    $line = '"' + ($timestamp, $TicketId, $Workflow, $UserPrincipalName, $Action, $Result, $safeDetails -join '","') + '"'
    Add-Content -Path $script:AuditLogPath -Value $line
}

function Get-RoleDefinition {
    param(
        [Parameter(Mandatory = $true)][string]$Role
    )

    $roleMap = Get-RoleMap
    if (-not ($roleMap.PSObject.Properties.Name -contains $Role)) {
        throw "Unknown role '$Role'. Add it to data/role_map.json before processing."
    }

    return $roleMap.$Role
}

function Test-AccessConflict {
    param(
        [array]$Groups = @()
    )

    $hasFinance = $Groups -contains "APP-Finance-Portal-Users"
    $hasCompliance = $Groups -contains "APP-Compliance-Casework"
    $hasPrivileged = $Groups -contains "ROLE-Privileged-Admins"
    $conflicts = @()

    if ($hasFinance -and $hasCompliance) {
        $conflicts += "Finance and Compliance access assigned together"
    }

    if ($hasPrivileged -and ($Groups | Where-Object { $_ -like "APP-Finance*" -or $_ -like "APP-Compliance*" })) {
        $conflicts += "Privileged admin access overlaps with business application access"
    }

    return $conflicts
}

function ConvertTo-Array {
    param([object]$Value)

    if ($null -eq $Value) {
        return @()
    }

    return @($Value)
}
