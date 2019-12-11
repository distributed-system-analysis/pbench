#Dockerfile for pbench-agent
FROM centos/tools
MAINTAINER Naga Ravi Chaitanya Elluri <nelluri@redhat.com>

# Setup pbench, sshd install dependencies
RUN rpm -ivh https://dl.fedoraproject.org/pub/epel/epel-release-latest-7.noarch.rpm && \
    curl -s https://copr.fedorainfracloud.org/coprs/ndokos/pbench-interim/repo/epel-7/ndokos-pbench-interim-epel-7.repo > /etc/yum.repos.d/copr-pbench.repo && \
    yum --enablerepo=ndokos-pbench-interim install -y configtools openssh-clients pbench-agent iproute sysvinit-tools \
    openssh-server git openssh-server openssh-clients initscripts ansible python-pip && \
    source /etc/profile.d/pbench-agent.sh && \
    curl -L https://github.com/openshift/origin/releases/download/v1.2.1/openshift-origin-client-tools-v1.2.1-5e723f6-linux-64bit.tar.gz | tar -zx && \
    mv openshift*/oc /usr/local/bin && \
    rm -rf openshift-origin-client-tools-* && \
    mkdir -p /root/.ssh && \ 
    pip install requests && \
    yum clean all && \
    sed -i "s/#Port 22/Port 2022/" /etc/ssh/sshd_config && \
    systemctl enable sshd

EXPOSE 2022

# Mount /proc
COPY mount.sh /root/mount.sh
COPY pbench.service /etc/systemd/system/pbench.service
RUN systemctl enable pbench.service

ENTRYPOINT ["/usr/sbin/init"]
