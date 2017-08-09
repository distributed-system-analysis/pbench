#Dockerfile for pbench-agent
FROM centos:latest
MAINTAINER Ravi Elluri <nelluri@redhat.com>

# Setup pbench
RUN curl -s https://copr.fedorainfracloud.org/coprs/ndokos/pbench/repo/epel-7/ndokos-pbench-epel-7.repo > /etc/yum.repos.d/copr-pbench.repo && \
    yum --enablerepo=ndokos-pbench install -y configtools openssh-clients pbench-agent pbench-sysstat iproute sysvinit-tools openssh-server git && \
    source /etc/profile.d/pbench-agent.sh && \
    curl -L https://github.com/openshift/origin/releases/download/v1.2.1/openshift-origin-client-tools-v1.2.1-5e723f6-linux-64bit.tar.gz | tar -zx && \
    mv openshift*/oc /usr/local/bin && \
    rm -rf openshift-origin-client-tools-*

# Install ansible
RUN mkdir -p /root/.ssh 
RUN yum install -y epel-release && yum install -y ansible

#Setting up systemd
ENV container docker
RUN yum -y swap -- remove fakesystemd -- install systemd systemd-libs
RUN yum -y update; yum clean all; \
(cd /lib/systemd/system/sysinit.target.wants/; for i in *; do [ $i == systemd-tmpfiles-setup.service ] || rm -f $i; done); \
rm -f /lib/systemd/system/multi-user.target.wants/*;\
rm -f /etc/systemd/system/*.wants/*;\
rm -f /lib/systemd/system/local-fs.target.wants/*; \
rm -f /lib/systemd/system/sockets.target.wants/*udev*; \
rm -f /lib/systemd/system/sockets.target.wants/*initctl*; \
rm -f /lib/systemd/system/basic.target.wants/*;\
rm -f /lib/systemd/system/anaconda.target.wants/*;
VOLUME [ "/sys/fs/cgroup" ]

# Setup sshd
RUN yum install -y openssh-server openssh-clients && yum clean all
RUN sed -i "s/#Port 22/Port 2022/" /etc/ssh/sshd_config
RUN systemctl enable sshd
EXPOSE 2022

# initscripts
RUN yum install -y initscripts && yum clean all

# Mount /proc
COPY mount.sh /root/mount.sh
COPY pbench-pod.service /etc/systemd/system/pbench-pod.service
RUN systemctl enable pbench-pod.service

ENTRYPOINT ["/usr/sbin/init"]
