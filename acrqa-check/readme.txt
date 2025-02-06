This runs out of zabbix on micvna:

$ cat /etc/zabbix/zabbix_agentd.d/userparameter_acrqa.conf
UserParameter=vna.acrqa[*],/home/micadmin/mictools/acrqa-check/acrqa_check.py $1

There is /var/lib/zabbix/.netrc for auth.
