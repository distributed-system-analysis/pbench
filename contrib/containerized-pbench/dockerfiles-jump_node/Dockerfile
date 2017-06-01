#Dockerfile for pbench-controller
FROM centos/tools
MAINTAINER Ravi Elluri <nelluri@redhat.com>

# Setup pbench
RUN curl -s https://copr.fedorainfracloud.org/coprs/ndokos/pbench/repo/epel-7/ndokos-pbench-epel-7.repo > /etc/yum.repos.d/copr-pbench.repo && \
    yum --enablerepo=ndokos-pbench install -y configtools openssh-clients pbench-agent pbench-sysstat iproute sysvinit-tools openssh-server git && \
    source /etc/profile.d/pbench-agent.sh && \
    curl -L https://github.com/openshift/origin/releases/download/v1.2.1/openshift-origin-client-tools-v1.2.1-5e723f6-linux-64bit.tar.gz | tar -zx && \
    mv openshift*/oc /usr/local/bin && \
    rm -rf openshift-origin-client-tools-*

# Install ansible and other dependencies
RUN mkdir -p /root/.ssh 
RUN yum install -y epel-release && yum install -y ansible
RUN yum -y install bind-utils blktrace ethtool findutils git gnuplot golang httpd-tools hwloc iotop iptables-services kernel ltrace mailx maven netsniff-ng net-tools ntp ntpdate numactl pciutils perf python-docker-py python-flask python-pip python-rbd python2-boto3 powertop psmisc rpm-build screen sos strace tar tcpdump tmux vim-enhanced xauth wget yum-utils rpmdevtools ceph-common glusterfs-fuse iscsi-initiator-utils

# setup pbench-ansible, svt
COPY pbench-agent.cfg /opt/pbench-agent/config/pbench-agent.cfg
WORKDIR /root
RUN git clone https://github.com/distributed-system-analysis/pbench.git && git clone https://github.com/openshift/svt.git
COPY script.sh script.sh
RUN chmod +x script.sh 

# Setup sshd
RUN yum install -y openssh-server openssh-clients && yum clean all
RUN sed -i "s/#Port 22/Port 2022/" /etc/ssh/sshd_config
RUN systemctl enable sshd
EXPOSE 2022

# initscripts
RUN yum install -y initscripts && yum clean all

# Run pbench as service
COPY pbench.service /etc/systemd/system/pbench.service
RUN systemctl enable pbench.service
ENTRYPOINT ["/usr/sbin/init"]
