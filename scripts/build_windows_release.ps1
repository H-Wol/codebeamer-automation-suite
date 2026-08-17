[CmdletBinding()]
param(
    [ValidateSet("Build", "Package", "All")]
    [string]$Mode = "All",

    [string]$ArtifactVersion = "",

    [string]$PythonCommand = "python"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepositoryRoot = [System.IO.Path]::GetFullPath(
    (Join-Path $PSScriptRoot "..")
)
$BuildRoot = Join-Path $RepositoryRoot "build/windows-release"
$PyInstallerWorkRoot = Join-Path $BuildRoot "pyinstaller-work"
$PyInstallerDistRoot = Join-Path $BuildRoot "pyinstaller-dist"
$DependencyManifest = Join-Path $BuildRoot "DEPENDENCIES.txt"
$ReleaseRoot = Join-Path $RepositoryRoot "release-artifacts"
$PortableRoot = Join-Path $ReleaseRoot "CodebeamerAutomationSuite"
$VersionFile = Join-Path $RepositoryRoot "VERSION"
$SpecFile = Join-Path $RepositoryRoot "packaging/CodebeamerAutomationSuite.spec"
$OfflineSampleRoot = Join-Path $RepositoryRoot "data/gui-offline-sample"
$PortableReadme = Join-Path $RepositoryRoot "packaging/README-WINDOWS.txt"

function Assert-RepositoryChildPath {
    param([Parameter(Mandatory = $true)][string]$Path)

    $fullPath = [System.IO.Path]::GetFullPath($Path)
    $separatorCharacters = [char[]]@(
        [System.IO.Path]::DirectorySeparatorChar,
        [System.IO.Path]::AltDirectorySeparatorChar
    )
    $repositoryPrefix = $RepositoryRoot.TrimEnd($separatorCharacters) + `
        [System.IO.Path]::DirectorySeparatorChar
    if (-not $fullPath.StartsWith(
        $repositoryPrefix,
        [System.StringComparison]::OrdinalIgnoreCase
    )) {
        throw "Refusing to modify a path outside the repository: $fullPath"
    }
}

function Remove-BuildDirectory {
    param([Parameter(Mandatory = $true)][string]$Path)

    Assert-RepositoryChildPath -Path $Path
    if (Test-Path -LiteralPath $Path) {
        Remove-Item -LiteralPath $Path -Recurse -Force
    }
}

function Invoke-Python {
    param([Parameter(Mandatory = $true)][string[]]$Arguments)

    & $PythonCommand @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Python command failed with exit code $LASTEXITCODE."
    }
}

function Copy-OfflineSample {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Destination
    )

    New-Item -ItemType Directory -Path $Destination -Force | Out-Null
    $blockedExtensions = @(".key", ".pem", ".p12", ".pfx")
    foreach ($sourceFile in Get-ChildItem -LiteralPath $Source -File -Recurse) {
        if (
            $sourceFile.Name -eq ".DS_Store" -or
            $sourceFile.Name.StartsWith(".env", [System.StringComparison]::OrdinalIgnoreCase) -or
            $blockedExtensions -contains $sourceFile.Extension.ToLowerInvariant()
        ) {
            continue
        }

        $relativePath = [System.IO.Path]::GetRelativePath($Source, $sourceFile.FullName)
        $destinationFile = Join-Path $Destination $relativePath
        $destinationDirectory = Split-Path -Parent $destinationFile
        New-Item -ItemType Directory -Path $destinationDirectory -Force | Out-Null
        Copy-Item -LiteralPath $sourceFile.FullName -Destination $destinationFile
    }
}

function Assert-PortableContents {
    param([Parameter(Mandatory = $true)][string]$Path)

    $blockedFiles = Get-ChildItem -LiteralPath $Path -File -Recurse | Where-Object {
        $_.Name -eq ".DS_Store" -or
        $_.Name.StartsWith(".env", [System.StringComparison]::OrdinalIgnoreCase)
    }
    if ($blockedFiles) {
        $paths = ($blockedFiles.FullName -join ", ")
        throw "Blocked file found in portable package: $paths"
    }
}

function Build-Application {
    if ($env:OS -ne "Windows_NT") {
        throw "Windows release builds must run on Windows."
    }
    if (-not (Test-Path -LiteralPath $VersionFile -PathType Leaf)) {
        throw "VERSION file is missing: $VersionFile"
    }

    Remove-BuildDirectory -Path $BuildRoot
    New-Item -ItemType Directory -Path $BuildRoot -Force | Out-Null

    $freezeOutput = & $PythonCommand -m pip freeze --all
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to collect the dependency manifest."
    }
    $freezeOutput | Sort-Object | Set-Content -LiteralPath $DependencyManifest -Encoding utf8NoBOM

    Invoke-Python -Arguments @(
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--workpath",
        $PyInstallerWorkRoot,
        "--distpath",
        $PyInstallerDistRoot,
        $SpecFile
    )

    $executable = Join-Path $PyInstallerDistRoot "CodebeamerAutomationSuite/CodebeamerAutomationSuite.exe"
    $internalDirectory = Join-Path $PyInstallerDistRoot "CodebeamerAutomationSuite/_internal"
    if (-not (Test-Path -LiteralPath $executable -PathType Leaf)) {
        throw "PyInstaller did not create the expected executable: $executable"
    }
    if (-not (Test-Path -LiteralPath $internalDirectory -PathType Container)) {
        throw "PyInstaller did not create the expected _internal directory."
    }
}

function Package-Application {
    $version = (Get-Content -LiteralPath $VersionFile -Raw).Trim()
    if ($version -notmatch "^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$") {
        throw "VERSION must contain an X.Y.Z version."
    }
    $effectiveArtifactVersion = $ArtifactVersion
    if ([string]::IsNullOrWhiteSpace($effectiveArtifactVersion)) {
        $effectiveArtifactVersion = "v$version"
    }
    if ($effectiveArtifactVersion -notmatch "^(v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(-rc\.(0|[1-9][0-9]*))?|dev-[0-9a-f]{7,40})$") {
        throw "ArtifactVersion must be a supported release tag or dev-<commit>."
    }
    if ($effectiveArtifactVersion.StartsWith("v", [System.StringComparison]::Ordinal)) {
        Invoke-Python -Arguments @(
            (Join-Path $RepositoryRoot "scripts/release_metadata.py"),
            "validate-tag",
            "--tag",
            $effectiveArtifactVersion,
            "--version-file",
            $VersionFile
        )
    }

    $PyInstallerOutput = Join-Path $PyInstallerDistRoot "CodebeamerAutomationSuite"
    $Executable = Join-Path $PyInstallerOutput "CodebeamerAutomationSuite.exe"
    $InternalDirectory = Join-Path $PyInstallerOutput "_internal"
    if (-not (Test-Path -LiteralPath $Executable -PathType Leaf)) {
        throw "Build output is missing: $Executable"
    }
    if (-not (Test-Path -LiteralPath $InternalDirectory -PathType Container)) {
        throw "Build output is missing: $InternalDirectory"
    }
    if (-not (Test-Path -LiteralPath $DependencyManifest -PathType Leaf)) {
        throw "Dependency manifest is missing: $DependencyManifest"
    }

    Remove-BuildDirectory -Path $ReleaseRoot
    New-Item -ItemType Directory -Path $PortableRoot -Force | Out-Null

    Copy-Item -LiteralPath $Executable -Destination $PortableRoot
    Copy-Item -LiteralPath $InternalDirectory -Destination $PortableRoot -Recurse
    Copy-Item -LiteralPath $DependencyManifest -Destination $PortableRoot
    Copy-Item -LiteralPath $PortableReadme -Destination (Join-Path $PortableRoot "README-WINDOWS.txt")
    Copy-OfflineSample `
        -Source $OfflineSampleRoot `
        -Destination (Join-Path $PortableRoot "sample")
    Assert-PortableContents -Path $PortableRoot

    $zipName = "Codebeamer-Automation-Suite-$effectiveArtifactVersion-windows-x64.zip"
    $zipPath = Join-Path $ReleaseRoot $zipName
    Compress-Archive -LiteralPath $PortableRoot -DestinationPath $zipPath -CompressionLevel Optimal

    $checksum = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash.ToLowerInvariant()
    "$checksum  $zipName" | Set-Content `
        -LiteralPath (Join-Path $ReleaseRoot "SHA256SUMS.txt") `
        -Encoding ascii

    Write-Host "Created portable release: $zipPath"
}

if ($Mode -eq "Build" -or $Mode -eq "All") {
    Build-Application
}
if ($Mode -eq "Package" -or $Mode -eq "All") {
    Package-Application
}
