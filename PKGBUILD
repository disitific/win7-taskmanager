# Maintainer: disitific on github
pkgname=win7-taskmanager
pkgver=1.0.0
pkgrel=1
pkgdesc="A remake of the Windows 7 Task Manager built with PyQt6 for Arch"
arch=('any')
url="https://github.com/disitific/win7-taskmanager"
license=('GPL')
depends=('python' 'python-pyqt6' 'python-psutil' 'wmctrl')
source=("main.py" "win7-taskmanager.desktop")
sha256sums=('SKIP'
            'SKIP')

package() {
    install -Dm755 "$srcdir/main.py" "$pkgdir/usr/share/$pkgname/main.py"
    install -Dm644 "$srcdir/win7-taskmanager.desktop" "$pkgdir/usr/share/applications/win7-taskmanager.desktop"

    install -d "$pkgdir/usr/bin"
    cat > "$pkgdir/usr/bin/win7-taskmanager" <<'EOF'
#!/usr/bin/env bash
exec python3 /usr/share/win7-taskmanager/main.py "$@"
EOF
    chmod 755 "$pkgdir/usr/bin/win7-taskmanager"
}
