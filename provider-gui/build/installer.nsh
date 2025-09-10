!macro customInstall
  ; Ensure a bin directory exists
  CreateDirectory "$INSTDIR\\bin"

  ; Copy CLI binary bundled in app resources to bin
  ; App resources path at runtime: $INSTDIR\resources\cli\win\golem-provider.exe (electron-builder)
  CopyFiles "$INSTDIR\\resources\\cli\\win\\golem-provider.exe" "$INSTDIR\\bin\\golem-provider.exe"

  ; Add install dir/bin to PATH (system-wide)
  ReadRegStr $0 HKLM "SYSTEM\\CurrentControlSet\\Control\\Session Manager\\Environment" "Path"
  StrCpy $1 "$INSTDIR\\bin"
  ; Check if already in PATH
  SearchPath $2 golem-provider.exe
  StrCmp $2 "$INSTDIR\\bin\\golem-provider.exe" done 0
  ; If not present, append
  StrLen $3 $0
  StrCpy $4 $0 $3
  StrCmp $4 "" 0 +2
    StrCpy $0 "$1"
    Goto +3
  StrCpy $0 "$0;$1"
  ; Write back
  WriteRegExpandStr HKLM "SYSTEM\\CurrentControlSet\\Control\\Session Manager\\Environment" "Path" $0
  ; Broadcast environment change
  System::Call 'USER32::SendMessageTimeoutA(p 0xffff, i ${WM_SETTINGCHANGE}, i 0, t "Environment", i 0, i 1000, *i .r0)'
done:
!macroend

!macro customUnInstall
  ; Remove from PATH (best-effort)
  ReadRegStr $0 HKLM "SYSTEM\\CurrentControlSet\\Control\\Session Manager\\Environment" "Path"
  Push $0
  Push ";$INSTDIR\\bin"
  Call un.RemoveFromPath
  Pop $0
  WriteRegExpandStr HKLM "SYSTEM\\CurrentControlSet\\Control\\Session Manager\\Environment" "Path" $0
  Delete "$INSTDIR\\bin\\golem-provider.exe"
!macroend

Function un.RemoveFromPath
 Exch $1
 Exch
 Exch $0
  Push $2
  Push $3
  Push $4
  Push $5
  StrCpy $2 $0
  StrLen $3 $1
 loop:
  StrCpy $4 $2 1
  StrCmp $4 ";" found
  StrCmp $4 "" done
  StrCpy $5 "$5$4"
  StrCpy $2 $2 -$3 ; shorten search string to prevent re-match
  Goto loop
 found:
  StrCpy $0 "$5"
 done:
  Pop $5
  Pop $4
  Pop $3
  Pop $2
  Pop $1
  Exch $0
FunctionEnd
