# Third-party notices

The project code is licensed under MIT. The Windows bundle also contains the
following third-party components, which retain their own licenses and notices:

| Component | Version in this build | License / notice |
| --- | --- | --- |
| CPython and bundled libraries | 3.12.4 | [Python license and included library notices](licenses/Python-LICENSE.txt) |
| Bleak | 3.0.2 | [MIT](licenses/bleak-MIT.txt) |
| typing_extensions | 4.16.0 | [Python Software Foundation license](licenses/typing_extensions.txt) |
| PyWinRT runtime and Windows projections | 3.2.1 | [MIT](licenses/PyWinRT-MIT.txt) |
| PyInstaller bootloader | 6.22.3 | [GPL with the PyInstaller bootloader exception](licenses/PyInstaller-COPYING.txt) |

PyWinRT source: https://github.com/pywinrt/pywinrt

The bundled PyWinRT projections are Windows.Devices.Bluetooth,
Windows.Devices.Bluetooth.Advertisement,
Windows.Devices.Bluetooth.GenericAttributeProfile, Windows.Devices.Enumeration,
Windows.Devices.Radios, Windows.Foundation, Windows.Foundation.Collections,
and Windows.Storage.Streams.

These notices describe this Windows build. If you rebuild with other versions,
update the notices and license copies to match the components you redistribute.
