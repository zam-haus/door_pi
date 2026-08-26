FROM docker.io/library/eclipse-mosquitto:2

COPY mosquitto.conf /mosquitto/config/mosquitto.conf
COPY passwordfile /mosquitto/config/passwordfile

# mosquitto drops privileges to the "mosquitto" user before reading the
# password file, so it needs to own it (the file is baked in owned by root).
RUN chown mosquitto:mosquitto /mosquitto/config/passwordfile

# The host may have its own mosquitto package installed, whose AppArmor
# profile has an explicit attachment path (/usr/sbin/mosquitto). On such
# hosts, the kernel auto-transitions any process executing that literal
# path into the host profile on exec -- regardless of container boundaries
# or --security-opt apparmor=unconfined -- and that profile only allows
# reading /etc/mosquitto/**, not this image's /mosquitto/config/. Running
# from a renamed copy avoids the path match entirely.
RUN cp /usr/sbin/mosquitto /usr/sbin/mosquitto-container

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["/usr/sbin/mosquitto-container", "-c", "/mosquitto/config/mosquitto.conf"]
