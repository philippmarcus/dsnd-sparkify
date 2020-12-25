# Script originally from: https://docs.aws.amazon.com/emr/latest/ReleaseGuide/emr-jupyterhub-pam-users.html
# Bulk add users to container and JupyterHub with temp password of username
set -x
# add all users seperated with spaces here
USERS=(philipp admin)
TOKEN=$(sudo docker exec jupyterhub /opt/conda/bin/jupyterhub token jovyan | tail -1)
for i in "${USERS[@]}"; 
do 
   sudo docker exec jupyterhub useradd -m -s /bin/bash -N $i
   sudo docker exec jupyterhub bash -c "echo $i:$i | chpasswd"
   curl -XPOST --silent -k https://$(hostname):9443/hub/api/users/$i \
 -H "Authorization: token $TOKEN" | cat | jq
done