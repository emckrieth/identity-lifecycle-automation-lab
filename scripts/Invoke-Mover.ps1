param(
    [string]$InputPath = ".\data\movers.csv",
    [string]$TicketId = "CHG-MOVER"
)

. "$PSScriptRoot\Common.ps1"

Initialize-LabOutput
$users = @(Get-LabUsers)
$requests = Import-Csv -Path $InputPath

foreach ($request in $requests) {
    $upn = $request.UserPrincipalName
    $user = $users | Where-Object { $_.UserPrincipalName -eq $upn } | Select-Object -First 1

    if (-not $user) {
        Write-AuditEntry -TicketId $request.TicketId -Workflow "Mover" -UserPrincipalName $upn -Action "FindUser" -Result "Failed" -Details "User not found"
        continue
    }

    try {
        $oldRole = $user.Role
        $oldGroups = @(ConvertTo-Array $user.Groups)
        $newRole = Get-RoleDefinition -Role $request.NewRole
        $newGroups = @(ConvertTo-Array $newRole.groups)

        $user.Department = $request.NewDepartment
        $user.Title = $request.NewTitle
        $user.Manager = $request.NewManager
        $user.Role = $request.NewRole
        $user.Groups = $newGroups
        $user.License = $newRole.license
        $user.MfaEnabled = [bool]$newRole.requiresMfa
        $user.LastReviewedDate = (Get-Date).ToString("yyyy-MM-dd")

        $removed = @($oldGroups | Where-Object { $newGroups -notcontains $_ })
        $added = @($newGroups | Where-Object { $oldGroups -notcontains $_ })
        $conflicts = @(Test-AccessConflict -Groups $newGroups)

        Write-AuditEntry -TicketId $request.TicketId -Workflow "Mover" -UserPrincipalName $upn -Action "UpdateRole" -Result "Success" -Details "$oldRole to $($request.NewRole)"
        Write-AuditEntry -TicketId $request.TicketId -Workflow "Mover" -UserPrincipalName $upn -Action "RemoveGroups" -Result "Success" -Details ($removed -join ";")
        Write-AuditEntry -TicketId $request.TicketId -Workflow "Mover" -UserPrincipalName $upn -Action "AddGroups" -Result "Success" -Details ($added -join ";")

        if ($conflicts.Count -gt 0) {
            Write-AuditEntry -TicketId $request.TicketId -Workflow "Mover" -UserPrincipalName $upn -Action "AccessConflictCheck" -Result "Warning" -Details ($conflicts -join ";")
        } else {
            Write-AuditEntry -TicketId $request.TicketId -Workflow "Mover" -UserPrincipalName $upn -Action "AccessConflictCheck" -Result "Success" -Details "No access conflicts detected"
        }
    } catch {
        Write-AuditEntry -TicketId $request.TicketId -Workflow "Mover" -UserPrincipalName $upn -Action "ProcessMover" -Result "Failed" -Details $_.Exception.Message
    }
}

Save-LabUsers -Users $users
Write-Host "Mover workflow complete. Review output/audit-log.csv."
