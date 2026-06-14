param(
    [string]$InputPath = ".\data\new_hires.csv",
    [string]$TicketId = "REQ-JOINER"
)

. "$PSScriptRoot\Common.ps1"

Initialize-LabOutput
$users = @(Get-LabUsers)
$requests = Import-Csv -Path $InputPath

foreach ($request in $requests) {
    $upn = $request.UserPrincipalName
    $existing = $users | Where-Object { $_.UserPrincipalName -eq $upn }

    if ($existing) {
        Write-AuditEntry -TicketId $request.TicketId -Workflow "Joiner" -UserPrincipalName $upn -Action "CreateUser" -Result "Skipped" -Details "User already exists"
        continue
    }

    try {
        $role = Get-RoleDefinition -Role $request.Role
        $groups = @(ConvertTo-Array $role.groups)
        $mfaRequired = [System.Convert]::ToBoolean($request.RequiresMfa)

        $newUser = [pscustomobject]@{
            EmployeeId = $request.EmployeeId
            UserPrincipalName = $upn
            DisplayName = $request.DisplayName
            Department = $request.Department
            Title = $request.Title
            Manager = $request.Manager
            Role = $request.Role
            Enabled = $true
            MfaEnabled = $mfaRequired
            License = $role.license
            Groups = $groups
            LastLoginDate = ""
            LastReviewedDate = (Get-Date).ToString("yyyy-MM-dd")
        }

        $users += $newUser
        Write-AuditEntry -TicketId $request.TicketId -Workflow "Joiner" -UserPrincipalName $upn -Action "CreateUser" -Result "Success" -Details "Created simulated user object"
        Write-AuditEntry -TicketId $request.TicketId -Workflow "Joiner" -UserPrincipalName $upn -Action "AssignGroups" -Result "Success" -Details ($groups -join ";")
        Write-AuditEntry -TicketId $request.TicketId -Workflow "Joiner" -UserPrincipalName $upn -Action "AssignLicense" -Result "Success" -Details $role.license
        Write-AuditEntry -TicketId $request.TicketId -Workflow "Joiner" -UserPrincipalName $upn -Action "SetMfa" -Result "Success" -Details "MFA enabled: $mfaRequired"
    } catch {
        Write-AuditEntry -TicketId $request.TicketId -Workflow "Joiner" -UserPrincipalName $upn -Action "ProcessJoiner" -Result "Failed" -Details $_.Exception.Message
    }
}

Save-LabUsers -Users $users
Write-Host "Joiner workflow complete. Review output/audit-log.csv."
