# install_pyrfc.ps1
# Helper script to guide installation of NW RFC SDK and pyrfc in the venv
# USAGE: Run from project root in an elevated PowerShell if needed.

Write-Host "1) NW RFC SDK gerekli. SAP Marketplace'ten indirin ve bir klasöre açın (ör. C:\nwrfcsdk)"
Write-Host "   - SAP S-user hesabı ile https://support.sap.com adresinden indirilir."
Write-Host "2) SDK yolunu ortam değişkeni olarak ayarlayın (User scope tavsiye edilir)."
Write-Host "   Örnek (PowerShell):"
Write-Host "     [Environment]::SetEnvironmentVariable('NWRFCSDK_HOME','C:\nwrfcsdk','User')"
Write-Host "     # PATH'e kütüphane dizinini ekleyin (oturum/PC yeniden başlatılmalı olabilir)"
Write-Host "     $old = [Environment]::GetEnvironmentVariable('PATH','User')"
Write-Host "     [Environment]::SetEnvironmentVariable('PATH', $old + ';C:\nwrfcsdk\lib', 'User')"
Write-Host "3) SDK yüklendikten sonra proje sanal ortamını kullanarak pyrfc yükleyin:"
Write-Host "   .\venv38\Scripts\python.exe -m pip install pyrfc"
Write-Host "4) Eğer kurulum hata verirse, hata çıktısını kopyalayın ve bana gönderin; gerekli build tools/redistributable adımlarını göstereyim."

# Otomatik deneme (isteğe bağlı): pip install pyrfc
if ($PSCmdlet.MyInvocation.BoundParameters.Count -eq 0) {
    Write-Host "\n-- Otomatik pip denemesi yapılıyor (venv38 kullanılacak)..."
    $py = Join-Path $PSScriptRoot "venv38\Scripts\python.exe"
    if (Test-Path $py) {
        & $py -m pip install pyrfc
    } else {
        Write-Host "venv38 bulunamadı. Lütfen önce sanal ortamı oluşturun veya path'i düzeltin." -ForegroundColor Yellow
    }
} else {
    Write-Host "Pip denemesi atlandı. Doğrudan talimatları uygulayın." -ForegroundColor Yellow
}
