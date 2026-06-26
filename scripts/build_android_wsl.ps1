$ErrorActionPreference = "Stop"

function Convert-ProxyForWsl {
    param(
        [string]$ProxyUri,
        [string]$WslHostAddress
    )

    if ([string]::IsNullOrWhiteSpace($ProxyUri)) {
        return $null
    }

    $uri = [Uri]$ProxyUri
    if ($uri.Host -in @("127.0.0.1", "localhost", "::1")) {
        $builder = [UriBuilder]$uri
        $builder.Host = $WslHostAddress
        return $builder.ToString().TrimEnd("/")
    }

    return $ProxyUri.TrimEnd("/")
}

$repo = (Resolve-Path ".").Path
$wslRepo = $repo -replace "^([A-Za-z]):", "/mnt/`$1" -replace "\\", "/"
$wslRepo = $wslRepo.ToLowerInvariant()
$pythonForAndroidRoot = Join-Path $repo ".buildozer\android\platform\python-for-android"
$pythonForAndroidBuild = Join-Path $pythonForAndroidRoot "pythonforandroid\build.py"
$pythonForAndroidRecipe = Join-Path $pythonForAndroidRoot "pythonforandroid\recipes\python3\__init__.py"
$pythonForAndroidStart = Join-Path $pythonForAndroidRoot "pythonforandroid\bootstraps\common\build\jni\application\src\start.c"
$pyjniusRecipe = Join-Path $pythonForAndroidRoot "pythonforandroid\recipes\pyjnius\__init__.py"

$wslGateway = (wsl.exe -d Ubuntu -- bash -lc "ip route show default | sed -n '1s/^default via \\([^ ]*\\).*/\\1/p'").Trim()
if (-not $wslGateway) {
    $wslGateway = (wsl.exe -d Ubuntu -- bash -lc "grep -m1 '^nameserver ' /etc/resolv.conf | sed 's/^nameserver //'").Trim()
}
if (-not $wslGateway) {
    throw "Unable to determine a WSL-reachable host address for proxy rewriting."
}

$rawHttpsProxy = if ($env:HTTPS_PROXY) { $env:HTTPS_PROXY } elseif ($env:https_proxy) { $env:https_proxy } else { "http://127.0.0.1:7897" }
$rawHttpProxy = if ($env:HTTP_PROXY) { $env:HTTP_PROXY } elseif ($env:http_proxy) { $env:http_proxy } else { $rawHttpsProxy }
$rawAllProxy = if ($env:ALL_PROXY) { $env:ALL_PROXY } elseif ($env:all_proxy) { $env:all_proxy } else { $rawHttpsProxy }

$wslHttpsProxy = Convert-ProxyForWsl -ProxyUri $rawHttpsProxy -WslHostAddress $wslGateway
$wslHttpProxy = Convert-ProxyForWsl -ProxyUri $rawHttpProxy -WslHostAddress $wslGateway
$wslAllProxy = Convert-ProxyForWsl -ProxyUri $rawAllProxy -WslHostAddress $wslGateway
$httpsProxyUri = [Uri]$wslHttpsProxy
$httpProxyUri = [Uri]$wslHttpProxy

$proxyExports = @"
export HTTP_PROXY='$wslHttpProxy'
export HTTPS_PROXY='$wslHttpsProxy'
export ALL_PROXY='$wslAllProxy'
export http_proxy='$wslHttpProxy'
export https_proxy='$wslHttpsProxy'
export all_proxy='$wslAllProxy'
export NO_PROXY='localhost,127.0.0.1,::1'
export no_proxy='localhost,127.0.0.1,::1'
export GRADLE_OPTS='-Dhttp.proxyHost=$($httpProxyUri.Host) -Dhttp.proxyPort=$($httpProxyUri.Port) -Dhttps.proxyHost=$($httpsProxyUri.Host) -Dhttps.proxyPort=$($httpsProxyUri.Port)'
export JAVA_TOOL_OPTIONS='-Dhttp.proxyHost=$($httpProxyUri.Host) -Dhttp.proxyPort=$($httpProxyUri.Port) -Dhttps.proxyHost=$($httpsProxyUri.Host) -Dhttps.proxyPort=$($httpsProxyUri.Port)'
"@

wsl.exe -d Ubuntu -- bash -lc "command -v java >/dev/null && command -v ant >/dev/null && command -v autoreconf >/dev/null && command -v libtoolize >/dev/null && command -v pkg-config >/dev/null && command -v dos2unix >/dev/null && python3 -m pip --version >/dev/null && dpkg -s libssl-dev libffi-dev libsqlite3-dev libbz2-dev libreadline-dev libncurses-dev libgdbm-dev tk-dev uuid-dev liblzma-dev >/dev/null 2>&1"
if ($LASTEXITCODE -ne 0) {
    throw "WSL Ubuntu is missing Java, Ant, Autotools, dos2unix, pkg-config, Python pip, and/or hostpython development libraries. Install prerequisites inside WSL, for example: sudo apt update && sudo apt install -y python3-pip python3-venv openjdk-17-jdk ant autoconf automake libtool pkg-config dos2unix build-essential git zip unzip libssl-dev libffi-dev libsqlite3-dev libbz2-dev libreadline-dev libncurses-dev libgdbm-dev tk-dev uuid-dev liblzma-dev"
}

if (Test-Path -LiteralPath $pythonForAndroidRecipe) {
    $recipeText = [System.IO.File]::ReadAllText($pythonForAndroidRecipe)
    if (-not $recipeText.Contains("'ac_cv_func_getgrgid=no'")) {
        $needle = "(?ms)^(\s*'ac_cv_little_endian_double=yes',\r?\n)(\s*'ac_cv_header_bzlib_h=no',)"
        $replacement = @'
$1        'ac_cv_little_endian_double=yes',
        # Android exposes getgrgid/getgrgid_r without the getgrent family on
        # some ABIs. Force-disable grp so the build does not reach
        # Modules/grpmodule.c and fail on undeclared setgrent/getgrent/endgrent.
        'ac_cv_func_getgrgid=no',
        'ac_cv_func_getgrgid_r=no',
        $2
'@
        if (-not [System.Text.RegularExpressions.Regex]::IsMatch($recipeText, $needle)) {
            throw "Failed to locate the python-for-android python3 configure_args block for the grp compatibility patch."
        }
        $patched = [System.Text.RegularExpressions.Regex]::Replace($recipeText, $needle, $replacement, 1)
        [System.IO.File]::WriteAllText($pythonForAndroidRecipe, $patched)
    }

    $recipeText = [System.IO.File]::ReadAllText($pythonForAndroidRecipe)
    if (-not $recipeText.Contains("Keep Python sources in the Android bundle")) {
        $callPatterns = @(
            "(?m)^(\s*)self\.compile_python_files\(modules_build_dir\)\r?$",
            "(?m)^(\s*)self\.compile_python_files\(join\(self\.get_build_dir\(arch\.arch\), 'Lib'\)\)\r?$",
            "(?m)^(\s*)self\.compile_python_files\(self\.ctx\.get_python_install_dir\(arch\.arch\)\)\r?$"
        )
        $matchedPatternCount = 0
        foreach ($pattern in $callPatterns) {
            if ([System.Text.RegularExpressions.Regex]::IsMatch($recipeText, $pattern)) {
                $recipeText = [System.Text.RegularExpressions.Regex]::Replace(
                    $recipeText,
                    $pattern,
                    '$1# Keep Python sources in the Android bundle to avoid early stdlib.zip bootstrap failures on Android/Python 3.12.',
                    1
                )
                $matchedPatternCount += 1
            }
        }
        if ($matchedPatternCount -ne $callPatterns.Count) {
            throw "Failed to locate the python-for-android python3 bundle compilation block for the stdlib source preservation patch."
        }
        [System.IO.File]::WriteAllText($pythonForAndroidRecipe, $recipeText)
    }

    $recipeText = [System.IO.File]::ReadAllText($pythonForAndroidRecipe)
    if (-not $recipeText.Contains("Preserve Python source files in stdlib/site-packages bundles")) {
        $stdlibNeedle = @'
    stdlib_filen_blacklist = [
        '*.py',
        '*.exe',
        '*.whl',
    ]
'@
        $stdlibReplacement = @'
    stdlib_filen_blacklist = [
        # Preserve Python source files in stdlib/site-packages bundles.
        '*.exe',
        '*.whl',
    ]
'@
        if (-not $recipeText.Contains($stdlibNeedle)) {
            throw "Failed to locate the python-for-android stdlib_filen_blacklist block for the source preservation patch."
        }
        $recipeText = $recipeText.Replace($stdlibNeedle, $stdlibReplacement)

        $sitePackagesNeedle = @'
    site_packages_filen_blacklist = [
        '*.py'
    ]
'@
        $sitePackagesReplacement = @'
    site_packages_filen_blacklist = [
        # Preserve Python source files in stdlib/site-packages bundles.
    ]
'@
        if (-not $recipeText.Contains($sitePackagesNeedle)) {
            throw "Failed to locate the python-for-android site_packages_filen_blacklist block for the source preservation patch."
        }
        $recipeText = $recipeText.Replace($sitePackagesNeedle, $sitePackagesReplacement)

        [System.IO.File]::WriteAllText($pythonForAndroidRecipe, $recipeText)
    }

    $recipeText = [System.IO.File]::ReadAllText($pythonForAndroidRecipe)
    if (-not $recipeText.Contains("Store stdlib.zip entries uncompressed for early codec bootstrap")) {
        $needle = "            shprint(sh.zip, '-X', stdlib_zip, *stdlib_filens)"
        $replacement = @"
            # Store stdlib.zip entries uncompressed for early codec bootstrap.
            shprint(sh.zip, '-0', '-X', stdlib_zip, *stdlib_filens)
"@
        if (-not $recipeText.Contains($needle)) {
            throw "Failed to locate the python-for-android stdlib zip command for the uncompressed bundle patch."
        }
        [System.IO.File]::WriteAllText($pythonForAndroidRecipe, $recipeText.Replace($needle, $replacement))
    }
}

if (Test-Path -LiteralPath $pythonForAndroidStart) {
    $startText = [System.IO.File]::ReadAllText($pythonForAndroidStart)
    if (-not $startText.Contains("Keep Python 3.12/3.13 on the legacy init path")) {
        $needle = "#define P4A_MIN_VER 11"
        $replacement = @'
#define P4A_MIN_VER 14
// Keep Python 3.12/3.13 on the legacy init path. The newer PyConfig-based
// bootstrap added for Python 3.14 can fail very early on Android while
// importing the filesystem codec, even when stdlib.zip is present.
'@
        if (-not $startText.Contains($needle)) {
            throw "Failed to locate the python-for-android bootstrap version gate in start.c."
        }
        [System.IO.File]::WriteAllText($pythonForAndroidStart, $startText.Replace($needle, $replacement))
    }
}

if (Test-Path -LiteralPath $pyjniusRecipe) {
    $pyjniusText = [System.IO.File]::ReadAllText($pyjniusRecipe)
    if (-not $pyjniusText.Contains("def lookup_prebuilt(self, arch):")) {
        $needle = @"
    patches = [
        ""use_cython.patch"",
        ('genericndkbuild_jnienv_getter.patch', will_build('genericndkbuild')),
        ('sdl3_jnienv_getter.patch', will_build('sdl3')),
    ]

"@
        $replacement = @"
    patches = [
        ""use_cython.patch"",
        ('genericndkbuild_jnienv_getter.patch', will_build('genericndkbuild')),
        ('sdl3_jnienv_getter.patch', will_build('sdl3')),
    ]

    def lookup_prebuilt(self, arch):
        # pyjnius is built from source in this workflow; prebuilt Android
        # wheels are not published for every ABI/platform tag combination.
        return False

"@
        if (-not $pyjniusText.Contains($needle)) {
            throw "Failed to locate the pyjnius recipe insertion point for disabling the prebuilt wheel lookup."
        }
        [System.IO.File]::WriteAllText($pyjniusRecipe, $pyjniusText.Replace($needle, $replacement))
    }
}

if (Test-Path -LiteralPath $pythonForAndroidBuild) {
    $buildText = [System.IO.File]::ReadAllText($pythonForAndroidBuild)
    if (-not $buildText.Contains("Patch bundled pip for Debian/Ubuntu ensurepip compatibility")) {
        $needle = "        shprint(host_python, '-m', 'venv', 'venv')"
        $replacement = @'
        shprint(host_python, '-m', 'venv', 'venv')

        # Patch bundled pip for Debian/Ubuntu ensurepip compatibility.
        resolvelib_structs = abspath(join(
            ctx.build_dir, 'venv', 'lib',
            'python' + ctx.python_recipe.major_minor_version_string,
            'site-packages', 'pip', '_vendor', 'resolvelib', 'structs.py'))
        if exists(resolvelib_structs):
            with open(resolvelib_structs, encoding='utf-8') as fileh:
                resolvelib_text = fileh.read()
            if 'RequirementInformation' not in resolvelib_text:
                if 'from collections import namedtuple' not in resolvelib_text:
                    resolvelib_text = resolvelib_text.replace(
                        'import itertools\n',
                        'import itertools\nfrom collections import namedtuple\n',
                        1,
                    )
                resolvelib_text = resolvelib_text.replace(
                    '\n\nclass DirectedGraph(object):\n',
                    "\n\nRequirementInformation = namedtuple(\n    'RequirementInformation', ['requirement', 'parent']\n)\nState = namedtuple(\n    'State', ['mapping', 'criteria', 'backtrack_causes']\n)\n\nclass DirectedGraph(object):\n",
                    1,
                )
                with open(resolvelib_structs, 'w', encoding='utf-8') as fileh:
                    fileh.write(resolvelib_text)
'@
        if (-not $buildText.Contains($needle)) {
            throw "Failed to locate the python-for-android build.py venv bootstrap block for the pip compatibility patch."
        }
        $buildText = $buildText.Replace($needle, $replacement)
        $needle = @'
(?ms)\s*info\('Upgrade pip to latest version'\)\r?\n\s*shprint\(sh\.bash, '-c', \(\r?\n\s*"source venv/bin/activate && pip install -U pip"\r?\n\s*\), _env=copy\.copy\(base_env\)\)\r?\n
'@
        if (-not [System.Text.RegularExpressions.Regex]::IsMatch($buildText, $needle)) {
            throw "Failed to remove the python-for-android pip self-upgrade step."
        }
        $buildText = [System.Text.RegularExpressions.Regex]::Replace($buildText, $needle, "", 1)
        [System.IO.File]::WriteAllText($pythonForAndroidBuild, $buildText)
    }
}

$wslBuildCommand = @'
set -euo pipefail
cd '__WSL_REPO__'
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
__PROXY_EXPORTS__

mkdir -p "$HOME/.buildozer/android/platform/apache-ant-1.9.4/bin"
ln -sf "$(command -v ant)" "$HOME/.buildozer/android/platform/apache-ant-1.9.4/bin/ant"

python_archive_source=""
for candidate in /home/ubuntu/v3.14.2.tar.gz /home/ubuntu/python-3.14.2.tar.gz; do
  if [ -f "$candidate" ]; then
    python_archive_source="$candidate"
    break
  fi
done

if [ -n "$python_archive_source" ]; then
  for recipe_name in hostpython3 python3; do
    recipe_dir="$PWD/.buildozer/android/platform/build-arm64-v8a_armeabi-v7a/packages/$recipe_name"
    mkdir -p "$recipe_dir"
    cp -f "$python_archive_source" "$recipe_dir/v3.14.2.tar.gz"
    touch "$recipe_dir/.mark-v3.14.2.tar.gz"
  done
fi

python3 -m venv .buildozer-venv
. .buildozer-venv/bin/activate
python -m pip install --upgrade pip buildozer cython==0.29.37
buildozer android debug
'@
$wslBuildCommand = $wslBuildCommand.Replace("__WSL_REPO__", $wslRepo).Replace("__PROXY_EXPORTS__", $proxyExports.Trim())

wsl.exe -d Ubuntu -- bash -lc $wslBuildCommand
if ($LASTEXITCODE -ne 0) {
    throw "Buildozer Android build failed with exit code $LASTEXITCODE"
}

$apk = Get-ChildItem -Path "bin" -Filter "*.apk" -ErrorAction SilentlyContinue | Select-Object -First 1
if ($apk) {
    New-Item -ItemType Directory -Force -Path "dist" | Out-Null
    Copy-Item -LiteralPath $apk.FullName -Destination "dist\EchoText-Android-v0.1.0-debug.apk" -Force
}
