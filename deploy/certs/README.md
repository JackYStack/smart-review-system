Place the production TLS files here before starting `docker-compose.production.yml`:

- `fullchain.pem`: server certificate plus intermediate certificates;
- `privkey.pem`: matching private key.

The PEM files are ignored by Git. Use a certificate issued for `PUBLIC_HOSTNAME`.
