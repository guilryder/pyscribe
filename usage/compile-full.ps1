[CmdletBinding(SupportsShouldProcess = $true)]
Param(
  [Bool]$PyScribe = $true,
  [Nullable[Bool]]$Xhtml = $null,
  [Bool]$Epub = $false,  # forces -Xhtml:1
  [Bool]$Mobi = $false,  # forces -Xhtml:1
  [Nullable[Bool]]$Latex = $null,
  [Bool]$Pdf = $false,  # forces -Latex:1
  [Bool]$AllText = $false,  # equivalent to -Latex:1 -Xhtml:1
  [String[]]$Sizes = @("small", "large"),
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
  $Xhtml = $true
  $Latex = $true
}
if ($Xhtml -eq $null) {
  $Xhtml = $Epub -or $Mobi
}
if ($Latex -eq $null) {
  $Latex = $Pdf
}

if ($Xhtml) {
  & $compile -Format:xhtml -View:$View -PyScribe:$PyScribe `
      -Epub:$Epub -Mobi:$Mobi -Files:$Files
}

if ($Latex) {
  foreach ($size in $Sizes) {
    & $compile -Format:latex -Size:$size -View:$View -PyScribe:$PyScribe `
        -Pdf:$Pdf -Files:$Files
  }
}
