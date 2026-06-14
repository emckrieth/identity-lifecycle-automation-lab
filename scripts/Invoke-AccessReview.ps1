param(
    [int]$StaleDays = 90
)

. "$PSScriptRoot\Common.ps1"

Initialize-LabOutput
$users = @(Get-LabUsers)
$today = Get-Date
$findings = @()

foreach ($user in $users) {
    $groups = @(ConvertTo-Array $user.Groups)
    $issues = @()

    if ($user.Enabled -and -not [bool]$user.MfaEnabled) {
        $issues += "MFA missing for enabled account"
    }

    if ([string]::IsNullOrWhiteSpace($user.Manager)) {
        $issues += "Missing manager"
    }

    if ($groups | Where-Object { $_ -like "ROLE-Privileged*" -or $_ -like "*Admins*" }) {
        $issues += "Privileged access requires review"
    }

    if (-not $user.Enabled -and $groups.Count -gt 0) {
        $issues += "Disabled account still has groups"
    }

    if (-not [string]::IsNullOrWhiteSpace($user.LastLoginDate)) {
        $lastLogin = [datetime]$user.LastLoginDate
        if (($today - $lastLogin).Days -ge $StaleDays) {
            $issues += "Stale account: no login in $StaleDays days"
        }
    }

    $conflicts = @(Test-AccessConflict -Groups $groups)
    $issues += $conflicts

    foreach ($issue in $issues) {
        $findings += [pscustomobject]@{
            UserPrincipalName = $user.UserPrincipalName
            DisplayName = $user.DisplayName
            Department = $user.Department
            Role = $user.Role
            Finding = $issue
            Enabled = $user.Enabled
            MfaEnabled = $user.MfaEnabled
            Groups = ($groups -join ";")
        }
    }
}

$findings | Export-Csv -Path $script:AccessReviewPath -NoTypeInformation
Write-AuditEntry -TicketId "ACCESS-REVIEW" -Workflow "AccessReview" -UserPrincipalName "all" -Action "GenerateReport" -Result "Success" -Details "$($findings.Count) findings written to output/access-review-report.csv"
Write-Host "Access review complete. Findings: $($findings.Count)."
