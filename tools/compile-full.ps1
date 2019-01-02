[CmdletBinding(SupportsShouldProcess = $true)]
Param(
  [Bool]$PyScribe = $true,
  [Nullable[Bool]]$Html = $null,
  [Bool]$Epub = $false,  # forces -Html:1
  [Bool]$Mobi = $false,  # forces -Html:1
  [Nullable[Bool]]$Latex = $null,
  [Bool]$Pdf = $false,  # forces -Latex:1
  [Bool]$AllText = $false,  # equivalent to -Html:1 -Latex:1
  [Bool]$View = $false,
  [String[]]$DefaultFiles,
  [Parameter(Position=0, ValueFromRemainingArguments)] $Files)

Set-StrictMode -Version Latest

$scriptDir = Split-Path (Resolve-Path $MyInvocation.MyCommand.Path)
$compile = Join-Path "$scriptDir" "compile.ps1"

if (!$Files) {
  $Files = $DefaultFiles
}

# Apply the parameter value implications.
if ($AllText) {
  $Html = $true
  $Latex = $true
}
if ($Html -eq $null) {
  $Html = $Epub -or $Mobi
}
if ($Latex -eq $null) {
  $Latex = $Pdf
}

if ($Html) {
  & $compile -Format:html -View:$View -PyScribe:$PyScribe `
      -Epub:$Epub -Mobi:$Mobi -Files:$Files
}

if ($Latex) {
  & $compile -Format:latex -View:$View -PyScribe:$PyScribe `
      -Pdf:$Pdf -Files:$Files
}
