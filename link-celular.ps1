# Mostra o endereço https:// do painel para abrir no celular (túnel da Cloudflare, no Docker)
# Uso, no terminal do VS Code aberto nesta pasta:  .\link-celular.ps1
# Se o túnel não estiver ligado, ele liga primeiro.
Set-Location $PSScriptRoot

$rodando = docker ps --filter "name=painel-oriximina-tunel" --filter "status=running" --format "{{.Names}}"
if (-not $rodando) {
    Write-Host "Ligando o túnel..."
    docker compose --profile celular up -d
}

# O endereço aparece no registro do túnel alguns segundos depois de ligar
for ($i = 0; $i -lt 30; $i++) {
    $linha = docker logs painel-oriximina-tunel 2>&1 | Select-String -Pattern "https://[a-z0-9-]+\.trycloudflare\.com" | Select-Object -Last 1
    if ($linha) {
        $endereco = $linha.Matches[0].Value
        Write-Host ""
        Write-Host "Abra no celular:  $endereco" -ForegroundColor Green
        Write-Host "(o endereço muda sempre que o túnel ou o Docker reiniciam)"
        Set-Clipboard -Value $endereco
        Write-Host "Endereço copiado para a área de transferência."
        exit 0
    }
    Start-Sleep -Seconds 1
}
Write-Host "Não achei o endereço. Veja o registro com:  docker logs painel-oriximina-tunel" -ForegroundColor Yellow
exit 1
