[CmdletBinding()]
# Run after the GitHub release workflow publishes the matching -arm64 tag to GHCR.
# This builds amd64 locally, copies both architectures to Docker Hub, and creates manifests.
param(
    [Parameter()]
    [string]$Version = "1.1.0",

    [Parameter()]
    [string]$DockerHubImage = "paladini/i-love-open-converter",

    [Parameter()]
    [string]$GitHubImage = "ghcr.io/paladini/i-love-open-converter"
)

$ErrorActionPreference = "Stop"

if ($Version -notmatch '^\d+\.\d+\.\d+$') {
    throw "Version must use semantic versioning, for example 1.0.0."
}

$repoRoot = Split-Path -Parent $PSScriptRoot
$localImage = "i-love-open-converter:publish-$Version"
$arm64Source = $GitHubImage + ":" + $Version + "-arm64"
$minorVersion = ($Version.Split('.')[0..1] -join '.')
$releaseTags = @($Version, $minorVersion, "latest")

function Invoke-Docker {
    param([Parameter(Mandatory)][string[]]$Arguments)
    & docker @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Docker command failed: docker $($Arguments -join ' ')"
    }
}

# Check for the CI-validated native ARM image before publishing any Docker Hub tags.
Invoke-Docker -Arguments @("buildx", "imagetools", "inspect", $arm64Source)

# Build and run the Dockerfile's offline smoke checks on the local native architecture.
Invoke-Docker -Arguments @(
    "buildx", "build", "--platform", "linux/amd64", "--load",
    "--tag", $localImage, $repoRoot
)

$architecture = (& docker image inspect $localImage --format '{{.Architecture}}').Trim()
if ($LASTEXITCODE -ne 0 -or $architecture -ne "amd64") {
    throw "Expected the local image to be amd64; got '$architecture'."
}

foreach ($tag in $releaseTags) {
    $amd64Tag = $DockerHubImage + ":" + $tag + "-amd64"
    Invoke-Docker -Arguments @("image", "tag", $localImage, $amd64Tag)
    Invoke-Docker -Arguments @("push", $amd64Tag)
}

# Copy the CI-built ARM image through the local Docker CLI so Docker Hub receives its layers.
Invoke-Docker -Arguments @("pull", "--platform", "linux/arm64", $arm64Source)
foreach ($tag in $releaseTags) {
    $arm64Tag = $DockerHubImage + ":" + $tag + "-arm64"
    Invoke-Docker -Arguments @("image", "tag", $arm64Source, $arm64Tag)
    Invoke-Docker -Arguments @("push", $arm64Tag)
}

# Publish universal tags that select the right native architecture for each Docker user.
foreach ($tag in $releaseTags) {
    $manifestTag = $DockerHubImage + ":" + $tag
    Invoke-Docker -Arguments @(
        "buildx", "imagetools", "create", "--tag", $manifestTag,
        ($DockerHubImage + ":" + $tag + "-amd64"),
        ($DockerHubImage + ":" + $tag + "-arm64")
    )
}

Write-Host "Published Docker Hub multi-platform tags for $DockerHubImage version $Version."
