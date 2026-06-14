param(
    [string]$InputPath = ".\data\leavers.csv",
    [string]$TicketId = "REQ-LEAVER"
)

. "$PSScriptRoot\Common.ps1"

Initialize-LabOutput
$users = @(Get-LabUsers)
$requests = Import-Csv -Path $InputPath

foreach ($request in $requests) {
    $upn = $request.UserPrincipalName
    $user = $users | Where-Object { $_.UserPrincipalName -eq $upn } | Select-Object -First 1

    if (-not $user) {
        Write-AuditEntry -TicketId $request.TicketId -Workflow "Leaver" -UserPrincipalName $upn -Action "FindUser" -Result "Failed" -Details "User not found"
        continue
    }

    $oldGroups = @(ConvertTo-Array $user.Groups)
    $privilegedGroups = @($oldGroups | Where-Object { $_ -like "ROLE-Privileged*" -or $_ -like "*Admins*" })

    $user.Enabled = $false
    $user.Groups = @()
    $user.License = ""
    $user.MfaEnabled = $false
    $user.LastReviewedDate = (Get-Date).ToString("yyyy-MM-dd")

    Write-AuditEntry -TicketId $request.TicketId -Workflow "Leaver" -UserPrincipalName $upn -Action "DisableAccount" -Result "Success" -Details "Account disabled"
    Write-AuditEntry -TicketId $request.TicketId -Workflow "Leaver" -UserPrincipalName $upn -Action "RemoveGroups" -Result "Success" -Details ($oldGroups -join ";")
    Write-AuditEntry -TicketId $request.TicketId -Workflow "Leaver" -UserPrincipalName $upn -Action "RemovePrivilegedGroups" -Result "Success" -Details ($privilegedGroups -join ";")
    Write-AuditEntry -TicketId $request.TicketId -Workflow "Leaver" -UserPrincipalName $upn -Action "RevokeLicense" -Result "Success" -Details "License removed"
    Write-AuditEntry -TicketId $request.TicketId -Workflow "Leaver" -UserPrincipalName $upn -Action "MailboxHandling" -Result "Success" -Details "$($request.MailboxAction); forward to $($request.ForwardTo)"
}

Save-LabUsers -Users $users
Write-Host "Leaver workflow complete. Review output/audit-log.csv."
