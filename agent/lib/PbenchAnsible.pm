#!/usr/bin/perl
# -*- mode: perl; indent-tabs-mode: t; perl-indent-level: 8 -*-
# Author: Andrew Theurer

package PbenchAnsible;
use strict;
use warnings;
use File::Basename;
my $pbench_lib_path;
my $script_path;
my $script_name;
BEGIN {
        $script_path = dirname($0);
        $script_name = basename($0);
        $pbench_lib_path = $script_path . "/postprocess";
}
use lib "$pbench_lib_path";
use Cwd 'abs_path';
use Exporter qw(import);
use List::Util qw(max);
use Data::Dumper;
use JSON;
use PbenchBase qw(get_hostname);
our @EXPORT_OK = qw(ssh_hosts ping_hosts copy_files_to_hosts copy_files_from_hosts remove_files_from_hosts remove_dir_from_hosts create_dir_hosts sync_dir_from_hosts verify_success stockpile_hosts);

my $script = "PbenchAnsible.pm";
my $sub;
my $ansible_bin = "ansible";
my $ansible_playbook_bin = "ansible-playbook";
my $inventory_opt = " --inventory /var/lib/pbench-agent/ansible-hosts";
my $ansible_base_cmdline = $ansible_bin;
my $ansible_playbook_cmdline = $ansible_playbook_bin;

sub verify_success {
	my $text_data = shift;
	$text_data =~ s/^[^\{]*//; # remove any junk before actual json
	my $data_ref = from_json($text_data);
	my %stats = %{ $$data_ref{"stats"}};
	for my $host (keys %stats) {
		if ($stats{$host}{"failures"} > 0 or $stats{$host}{"unreachable"} > 0) {
 			print "host $host failed";
			return 0;
		}
	}
	return 1;
}
sub get_ansible_logdir { # create a directory to store ansible files
	my $basedir = shift;
	my $action = shift;
	my $logdir = $basedir . "/ansible-log/";
	mkdir($logdir);
	$logdir = $logdir . time . "-" . $action;
	mkdir($logdir);
	return $logdir;
}
sub log_ansible { # log the comand line and its output
	my $logdir = shift;
	my $cmd = shift;
	my $output = shift;
	mkdir($logdir);
	my $fh;
	open($fh, ">" . $logdir . "/command.txt") or die "Could not open $logdir/command.txt";
	print $fh $cmd;
	close $fh;
	open($fh, ">" . $logdir . "/output.json") or die "Could not open $logdir/output.json";
	print $fh $output;
	close $fh;
}
sub build_inventory { # create an inventory file with hosts
	my $hosts_ref = shift;
	my $logdir = shift;
	my $file = $logdir . "/hosts";
	my $fh;
	open($fh, ">", $file) or die "Could not create the inventory file $file";
	for my $h (@$hosts_ref) {
		print $fh "$h\n";
	}
	close $fh;
	return $file;
}
sub build_stockpile_inventory { # create an inventory file with hosts
	my $hosts_ref = shift;
	my $logdir = shift;
	my $file = $logdir . "/hosts";
	my $fh;
	open($fh, ">", $file) or die "Could not create the inventory file $file";
	print $fh "[all]\n";
	for my $h (@$hosts_ref) {
		print $fh "$h\n";
	}
	print $fh "[stockpile]\n";
	printf $fh "%s\n", get_hostname;
	close $fh;
	return $file;
}
sub build_playbook { # create the playbok file
	my $playbook_ref = shift;
	my $logdir = shift;
	my $fh;
	my $file = $logdir . "/playbook.json";
	open($fh, ">", $file) or die "Could not create the playbook file $file";
	printf $fh "%s", to_json( $playbook_ref, { ascii => 1, pretty => 1, canonical => 1 } );
	close $fh;
	return $file;
}
sub run_playbook { # execute a playbook
	my $playbook_ref = shift;
	my $inv_file = shift;
	my $logdir = shift;
	my $extra_vars = shift;
	my $extra_vars_opt = "";
	if ($extra_vars) {
		$extra_vars_opt = " --extra-vars " . $extra_vars . " ";
	}
	my $playbook_file = build_playbook($playbook_ref, $logdir);
	my $full_cmd = "ANSIBLE_CONFIG=/var/lib/pbench-agent/ansible.cfg " .
			$ansible_playbook_cmdline . $extra_vars_opt . " -i " .  $inv_file . " " . $playbook_file;
	my $output = `$full_cmd`;
	log_ansible($logdir, $full_cmd, $output);
	if ($? == 0 and verify_success($output)) {
		return $output;
	} else {
		print "Execution of this Ansible playbook failed\n";
		printf "playbook file: %s\n", $playbook_file;
		exit 1;
	}
}
sub ping_hosts { # check for connectivity with ping
	my $hosts_ref = shift;
	my $basedir = shift; # we create a new dir under this and log all Ansible files and output
	my $logdir = get_ansible_logdir($basedir, "ping_hosts");
	my $inv_file = build_inventory($hosts_ref, $logdir);
	my $full_cmd = "ANSIBLE_CONFIG=/var/lib/pbench-agent/ansible.cfg " .
			$ansible_base_cmdline . " -i " .  $inv_file . " all -m ping";
	my $output = `$full_cmd`;
	log_ansible($logdir, $full_cmd, $output);
	if (verify_success($output)) {
		return $output;
	} else {
		print "Execution of this Ansible playbook failed\n";
		printf "Ansible log dir: %s\n", $logdir;
		exit 1;
	}
}
sub stockpile_hosts { # run stockpile against these hosts
	my $hosts_ref = shift; # array-reference to host list, with the first host being the 'stockpile' host
	my $basedir = shift;
	my $extra_vars = shift;
	my $logdir = get_ansible_logdir($basedir, "stockpile_hosts");
	system('cp -a /tmp/stockpile/* ' . $logdir);
	my $inv_file = build_stockpile_inventory($hosts_ref, $logdir);
	my %play;
	my @playbook;
	my @roles1 = qw(yum_repos);
	my %play1 = ( "hosts" => "all", "remote_user" => "root", "become" => JSON::true, "roles" => \@roles1);
	push(@playbook, \%play1);
	my @roles2 = qw(dump-facts);
	my %play2 = ( "hosts" => "stockpile", "gather_facts" => JSON::false, "remote_user" => "root", "roles" => \@roles2);
	push(@playbook, \%play2);
	return run_playbook(\@playbook, $inv_file, $logdir, $extra_vars);
}
sub create_dir_hosts { # creates a directory on remote hosts
	my $hosts_ref = shift; # array-reference to host list to copy from 
	my $dir = shift; # the directory to create
	my $basedir = shift;
	my $logdir = get_ansible_logdir($basedir, "create_dir_hosts");
	my $inv_file = build_inventory($hosts_ref, $logdir);
	my @tasks;
	my %task = ( "name" => "create dir on hosts", "file" => "path=" . $dir . " state=directory" );
	push(@tasks, \%task);
	my %play = ( hosts => "all", tasks => \@tasks );;
	my @playbook = (\%play);;
	return run_playbook(\@playbook, $inv_file, $logdir);
}
sub ssh_hosts { # run a command on remote hosts
	my $hosts_ref = shift; # array-reference to host list
	my $cmd = shift; # array-refernce to file list
	my $chdir = shift; # directory to run command
	my $basedir = shift;
	my $logdir = get_ansible_logdir($basedir, "ssh_hosts");
	my $inv_file = build_inventory($hosts_ref, $logdir);
	my @tasks;
	my %task = ( name => "run cmd on hosts", command => $cmd . " chdir=" . $chdir);
	push(@tasks, \%task);
	my %play = ( hosts => "all", tasks => \@tasks );;
	my @playbook = (\%play);;
	return run_playbook(\@playbook, $inv_file, $logdir);
}
sub copy_files_to_hosts { # copies local files to hosts with a new, common destination path
	my $hosts_ref = shift; # array-reference to host list
	my $src_files_ref = shift; # array-refernce to file list
	my $dst_path = shift; # a single destination path
	my $basedir = shift;
	my $logdir = get_ansible_logdir($basedir, "copy_files_to_hosts");
	my $inv_file = build_inventory($hosts_ref, $logdir);
	my @tasks;
	for my $src_file (@$src_files_ref) {
		my %task = ( name => "copy files to hosts", copy => "src=" . $src_file . " dest=" . $dst_path . "/" . basename($src_file) );
		push(@tasks, \%task);
	}
	my %play = ( hosts => "all", tasks => \@tasks );;
	my @playbook = (\%play);
	return run_playbook(\@playbook, $inv_file, $logdir);
}
sub copy_files_from_hosts { # copies files from remote hosts to a local path which includes $hostbname directory
	my $hosts_ref = shift; # array-reference to host list to copy from 
	my $src_files_ref = shift; # array-refernce to file list to fetch
	my $src_path = shift; # a single src path where all files in list can be found
	my $dst_path = shift;
	my $basedir = shift;
	if (!$dst_path) {
		$dst_path="/tmp/";
	}
	my $logdir = get_ansible_logdir($basedir, "copy_files_from_hosts");
	my $inv_file = build_inventory($hosts_ref, $logdir);
	my @tasks;
	for my $src_file (@$src_files_ref) {
		my %task = ( "name" => "copy files from hosts", "fetch" => "flat=yes " . "src=" .
			     $src_path . "/" . $src_file . " dest=" .  $dst_path .
			     "/{{ inventory_hostname }}/" . $src_file);
		push(@tasks, \%task);
	}
	my %play = ( hosts => "all", tasks => \@tasks );;
	my @playbook = (\%play);;
	return run_playbook(\@playbook, $inv_file, $logdir);
}
sub sync_dir_from_hosts { # copies files from remote hosts to a local path which includes $hostbname directory
	my $hosts_ref = shift; # array-reference to host list to copy from 
	my $src_dir = shift; # the dir to sync from on the hosts
	my $dst_dir = shift; # a single dst dir where all the remote host dirs will be sync'd to, first with a dir=hostname
	my $basedir = shift;
	my $logdir = get_ansible_logdir($basedir, "sync_dir_from_hosts");
	my $inv_file = build_inventory($hosts_ref, $logdir);
	my @tasks;
	my %task = ( "name" => "sync dirs from hosts", "synchronize" => "mode=pull src=" . $src_dir . " dest=" . $dst_dir .
		     "/{{ inventory_hostname }}/");
	push(@tasks, \%task);
	my %play = ( hosts => "all", tasks => \@tasks );;
	my @playbook = (\%play);
	return run_playbook(\@playbook, $inv_file, $logdir);
}
sub remove_files_from_hosts { # copies files from remote hosts to a local path which includes $hostbname directory
	my $hosts_ref = shift; # array-reference to host list to copy from 
	my $src_files_ref = shift; # array-refernce to file list to fetch
	my $src_path = shift; # a single src path where all files in list can be found
	my $basedir = shift;
	my $logdir = get_ansible_logdir($basedir, "remove_files_from_hosts");
	my $inv_file = build_inventory($hosts_ref, $logdir);
	my @tasks;
	for my $src_file (@$src_files_ref) {
		my %task = ( "name" => "remove files from hosts", "file" => "path=" . $src_path . "/" . $src_file . " state=absent" );
		push(@tasks, \%task);
	}
	my %play = ( hosts => "all", tasks => \@tasks );;
	my @playbook = (\%play);
	return run_playbook(\@playbook, $inv_file, $logdir);
}
sub remove_dir_from_hosts { # copies files from remote hosts to a local path which includes $hostbname directory
	my $hosts_ref = shift; # array-reference to host list to copy from 
	my $dir = shift; # the directory to delete
	my $basedir = shift;
	my $logdir = get_ansible_logdir($basedir, "remove_dir_from_hosts");
	my $inv_file = build_inventory($hosts_ref, $logdir);
	my @tasks;
	my %task = ( "name" => "remove dir from hosts", "file" => "path=" . $dir . " state=absent" );
	push(@tasks, \%task);
	my %play = ( hosts => "all", tasks => \@tasks );;
	my @playbook = (\%play);;
	return run_playbook(\@playbook, $inv_file, $logdir);
}
1;
