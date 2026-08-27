# OTA / recovery signing key

`testkey.x509.pem` + `testkey.pk8` are the **AOSP public test key**
(build/target/product/security/testkey). This device verifies recovery-flashed
zips against this exact cert: it is the single certificate inside the device's
`otacerts.zip` (both in the recovery ramdisk and on the system partition),
sha256 `A4:0D:A8:0A:59:D1:70:CA:A9:50:CF:15:C1:8C:45:4D:47:A3:9B:26:98:9D:8B:64:0E:CD:74:5B:A7:1B:F5:DC`,
subject `O=Android, CN=Android, android@android.com`.

It is a public, well-known key (not a secret), the whole device is a test-keys
build. A zip signed with it (whole-file OTA signature, `signapk -w`) passes the
recovery `verify_file` check. Fastbootd flashing does not use this key at all.
