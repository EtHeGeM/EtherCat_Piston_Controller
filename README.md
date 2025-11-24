# Hidrolik Piston PLC / HMI (EtherCAT)

Üç hidrolik piston için Python/Tkinter ile hazırlanmış örnek PLC simülasyonu. Mimari server (HMI/master) ve client (piston kontrolü) olarak ayrıldı; aradaki haberleşme EtherCAT düşünülerek Fake EtherCAT Bus veya pysoem üzerinden kurulabilir.

## Özellikler
- 3 piston, her biri için ayrı uzatma ve geri çekme süre (saniye) ayarı
- Start (Latch) ve Stop; latch açıkken döngü otomatik tekrar eder
- Latching olmadan tek döngü komutu
- EtherCAT master (HMI) -> slave (piston client) komut akışı, durum geri bildirimi
- Varsayılan süreleri geri yükleme, siyah log alanı ile izleme

## Kurulum
```bash
# pysoem gerçek EtherCAT master denemeleri için (opsiyonel); Fake bus için şart değil
pip install -r requirements.txt
```

## Çalıştırma (demo/fake EtherCAT)
- Tek komutla HMI (server) + piston client (slave) aynı proses içinde başlatılır:
  ```bash
  python3 main.py
  ```
- HMI açıldığında client otomatik devreye girer ve EtherCAT bus üzerinden komutları dinler.
- `piston_client.py` client kodunu ayrı olarak incelemek/çalıştırmak için kullanılabilir; Fake bus in-memory olduğundan gerçek iletişim için aynı proses veya gerçek EtherCAT kurulumu gerekir.

## Streamlit arayüzü
- GUI yerine web tabanlı arayüz için:
  ```bash
  streamlit run streamlit_app.py
  ```
- Start/Stop/Tek döngü komutlarını ve piston sürelerini kontrol edebilir, server ve client loglarını aynı ekranda takip edebilirsiniz.

## Gerçek EtherCAT'e uyarlama
- `ethercat_bus.create_bus(interface_name)` fonksiyonunda pysoem ekran kartı/master kurulumu eklenebilir. Arayüz adı verilerek gerçek master devreye alındığında HMI tarafı yine `create_bus()` ile aynı API üzerinden komut yazar/okur.

## Kullanım Notları
- `Start (Latch)`: latching kontaktörünü açar, EtherCAT üzerinden client'a süreler ve start komutu gönderir.
- `Stop`: latching'i kapatır ve client'ı durdurur.
- `Tek Döngü`: latch kullanmadan yalnızca bir çevrim çalıştırır.
- Süreler saniye cinsindedir; 0.1–30 arası değerler girilebilir. Var olan değerleri değiştirip yeni komut göndererek anlık testler yapabilirsiniz.
- HMI üzerindeki **Sinyal İzleyici** bölümünde start/stop pulse'ları, latch, running ve piston aktif sinyalleri (son 20 sn) canlı akış olarak gösterilir.
