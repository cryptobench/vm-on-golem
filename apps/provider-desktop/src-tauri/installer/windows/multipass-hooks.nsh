!include LogicLib.nsh

!macro NSIS_HOOK_POSTINSTALL
  DetailPrint "Verifying Multipass"
  nsExec::ExecToLog 'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$INSTDIR\multipass\install-multipass.ps1" -InstallerPath "$INSTDIR\multipass\multipass-1.16.2+win-win64.msi" -MinVersion "1.13.0"'
  Pop $0
  ${If} $0 != 0
    MessageBox MB_ICONSTOP "Multipass could not be installed or verified. The provider desktop installation cannot continue."
    Abort "Multipass installation failed"
  ${EndIf}
!macroend
