[CmdletBinding(SupportsShouldProcess = $true)]
Param(
  [String]$Format = "latex",
  [String]$Size = "large",
  [Bool]$View = $false,
  [Bool]$PyScribe = $true,
  [Bool]$Epub = $false,
  [Bool]$Mobi = $false,
  [Bool]$Pdf = $false,
  [Parameter(Position=0, Mandatory, ValueFromPipeline)] $Files)

begin {
  Set-StrictMode -Version Latest

  $usageDir = Split-Path (Resolve-Path $MyInvocation.MyCommand.Path)
  $pyscribeDir = Split-Path ($usageDir)
  $pyscribeScript = Join-Path "$pyscribeDir" "pyscribe.py"

  # Allow using core.cls; relative paths generate warnings.
  $env:TEXINPUTS="$usageDir;"

  function EbookConvert {
    Param(
      [String]$Basename,
      [String]$OutputExtension,
      [Parameter(ValueFromRemainingArguments)] $ExtraArgs)
    & "C:\Program Files\Calibre\ebook-convert.exe" `
      "${Basename}.html" "${Basename}.${OutputExtension}" `
      $ExtraArgs
  }

  $operation = "compile $Format $Size"
  if ($PyScribe) { $operation = "$operation PyScribe" }
  if ($View) { $operation = "$operation View" }
  switch ($Format) {
    "xhtml" {
      if ($Epub) { $operation = "$operation Epub" }
      if ($Mobi) { $operation = "$operation Mobi" }
    }
    "latex" {
      if ($Pdf) { $operation = "$operation Pdf" }
    }
  }
}

process {
  foreach ($filename in $Files) {
    $basename = [IO.Path]::GetFileNameWithoutExtension($filename)
    If (!$PSCmdlet.ShouldProcess($filename, $operation)) {
      continue
    }

    $basenamesize = "${basename} - ${Size}"

    echo ""
    echo "### Processing ${filename} - format: $Format - size: $Size"
    if ($PyScribe) {
      echo "Compiling PyScribe source..."
      & $pyscribeScript --format=$Format -d device.size=$Size "$filename"
    }

    Push-Location "output"
    switch ($Format) {
      "xhtml" {
        if ($PyScribe -and $View) {
          & ".\${basename}.html"
        }
        if ($Epub) {
          echo "Compiling ${filename}.html to ePub..."
          EbookConvert $basename "epub" --dont-split-on-page-breaks --no-default-epub-cover
        }
        if ($Mobi) {
          echo "Compiling ${filename}.html to MOBI..."
          EbookConvert $basename "mobi" --no-inline-toc
        }
      }
      "latex" {
        if ($Pdf) {
          echo "Compiling ${basenamesize}.tex to PDF..."
          texify --batch --pdf --clean --quiet "${basenamesize}.tex"
        }
        if ($Pdf -and $View -and (Test-Path "${basenamesize}.pdf")) {
          & ".\${basenamesize}.pdf"
        }
      }
    }
    Pop-Location
  }
}
