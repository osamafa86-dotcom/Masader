#!/bin/sh
# Daily compressed pg_dump of the marsad database into /backups, keeping BACKUP_KEEP_DAYS days.
set -eu
while true; do
  stamp=$(date -u +%Y-%m-%dT%H%M)
  pg_dump -h db -U marsad -Fc marsad > "/backups/marsad-$stamp.dump.tmp"
  mv "/backups/marsad-$stamp.dump.tmp" "/backups/marsad-$stamp.dump"
  echo "backup written: marsad-$stamp.dump"
  find /backups -name 'marsad-*.dump' -mtime +"${BACKUP_KEEP_DAYS:-14}" -delete
  sleep 86400
done
