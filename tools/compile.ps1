[CmdletBinding(SupportsShouldProcess = $true)]
Param(
  [String]$Format = "latex",
  [Bool]$View = $false,
  [Bool]$PyScribe = $true,
  [Bool]$Epub = $false,
  [Bool]$Mobi = $false,
  [Bool]$Pdf = $false,
  [Parameter(Position=0, Mandatory, ValueFromPipeline)] $Files)

begin {
  Set-StrictMode -Version Latest

  $scriptDir = Split-Path (Resolve-Path $MyInvocation.MyCommand.Path)
  $pyscribeDir = Split-Path $scriptDir
  $libDir = Join-Path $pyscribeDir "lib"
  $pyscribeScript = Join-Path $pyscribeDir "pyscribe.py"
  $outDir = "output"

  function EbookConvert {
    Param(
      [String]$Basename,
      [String]$OutputExtension,
      [Parameter(ValueFromRemainingArguments)] $ExtraArgs)
    & "C:\Program Files\Calibre\ebook-convert.exe" `
      "${Basename}.html" "${Basename}.${OutputExtension}" `
      --toc-filter="\[[0-9]+\]" `
      $ExtraArgs
  }

  $operation = "compile $Format"
  if ($PyScribe) { $operation = "$operation PyScribe" }
  if ($View) { $operation = "$operation View" }
  switch ($Format) {
    "html" {
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

    echo ""
    echo "### Processing ${filename} - format: $Format"
    if ($PyScribe) {
      echo "Compiling PyScribe source..."
      & $pyscribeScript --output=$outDir --format=$Format "$filename"
    }

    Push-Location $outDir
    switch ($Format) {
      "html" {
        if ($PyScribe -and $View) {
          & ".\${basename}.html"
        }
        if ($Epub) {
          echo "Compiling ${filename}.html to ePub..."
          EbookConvert $basename "epub" --dont-split-on-page-breaks --no-default-epub-cover
        }
        if ($Mobi) {
          echo "Compiling ${filename}.html to MOBI..."
          EbookConvert $basename "mobi" --no-inline-toc --mobi-keep-original-images --cover=nul
        }
      }
      "latex" {
        if ($Pdf) {
          echo "Compiling ${basename}.tex to PDF..."
          texify -I $libDir --batch --pdf --clean --quiet "${basename}.tex"
        }
        if ($Pdf -and $View -and (Test-Path "${basename}.pdf")) {
          & ".\${basename}.pdf"
        }
      }
    }
    Pop-Location
  }
}
