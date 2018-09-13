#!/usr/bin/perl
# -*- mode: perl; indent-tabs-mode: t; perl-indent-level: 8 -*-
# Author: Andrew Theurer

package PbenchAnsible;
use strict;
use warnings;
use File::Basename;
use Cwd 'abs_path';
use Exporter qw(import);
use List::Util qw(max);
use Data::Dumper;
use JSON;

our @EXPORT_OK = qw(ssh_hosts ping_hosts copy_files_to_hosts copy_files_from_hosts remove_files_from_hosts create_dir_hosts sync_dir_from_hosts);

my $script = "PbenchAnsible.pm";
my $sub;
my $ansible_bin = "ansible";
my $ansible_playbook_bin = "ansible-playbook";
my $inventory_opt = " --inventory /var/lib/pbench-agent/ansible-hosts";
my $ansible_base_cmdline = $ansible_bin;
my $ansible_playbook_cmdline = $ansible_playbook_bin;

sub build_inventory {
	my $hosts_ref = shift;
	my $fh;
	my $file = `mktemp`;
	chomp $file;
	open($fh, ">", $file) or die "Could not create the inventory file";
	for my $h (@$hosts_ref) {
		print $fh "$h\n";
	}
	close $fh;
	return $file;
}
sub build_playbook {
	my $playbook_ref = shift;
	my $fh;
	my $file = `mktemp`;
	chomp $file;
	open($fh, ">", $file) or die "Could not create the playbook file";
	printf $fh "%s", to_json( $playbook_ref, { ascii => 1, pretty => 1, canonical => 1 } );
	close $fh;
	return $file;
}
sub ping_hosts {
	my $hosts_ref = shift;
	my $inv_file = build_inventory($hosts_ref);
	my $full_cmd = "ANSIBLE_CONFIG=/var/lib/pbench-agent/ansible.cfg " .
			$ansible_base_cmdline . " -i " .  $inv_file . " all -m ping";
	print "ansible cmdline:\n$full_cmd\n";
	my $output = `$full_cmd`;
	unlink $inv_file;
	return $output;
}
sub ssh_hosts {
	my $hosts_ref = shift; # array-reference to host list
	my $cmd = shift; # array-refernce to file list
	my $dir = shift; # directory to run command
	my $inv_file = build_inventory($hosts_ref);
	my @tasks;
	my %task = ( name => "run cmd on hosts", command => $cmd . " chdir=" . $dir);
	push(@tasks, \%task);
	my %play = ( hosts => "all", tasks => \@tasks );;
	my @playbook = (\%play);;
	my $playbook_file = build_playbook(\@playbook);
	my $full_cmd = "ANSIBLE_CONFIG=/var/lib/pbench-agent/ansible.cfg " .
			$ansible_playbook_cmdline . " -i " .  $inv_file . " " . $playbook_file;
	print "ansible cmdline:\n$full_cmd\n";
	my $output = `$full_cmd`;
	unlink $inv_file, $playbook_file;
	return $output;
}
sub copy_files_to_hosts { # copies local files to hosts with a new, common destination path
	my $hosts_ref = shift; # array-reference to host list
	my $src_files_ref = shift; # array-refernce to file list
	my $dst_path = shift; # a single destination path
	my $inv_file = build_inventory($hosts_ref);
	my @tasks;
	for my $src_file (@$src_files_ref) {
		my %task = ( name => "copy files to hosts", copy => "src=" . $src_file . " dest=" . $dst_path . "/" . basename($src_file) );
		push(@tasks, \%task);
	}
	my %play = ( hosts => "all", tasks => \@tasks );;
	my @playbook = (\%play);;
	my $playbook_file = build_playbook(\@playbook);
	my $full_cmd = "ANSIBLE_CONFIG=/var/lib/pbench-agent/ansible.cfg " .
			$ansible_playbook_cmdline . " -i " .  $inv_file . " " . $playbook_file;
	print "ansible cmdline:\n$full_cmd\n";
	my $output = `$full_cmd`;
	unlink $inv_file, $playbook_file;
	return $output;
}
sub copy_files_from_hosts { # copies files from remote hosts to a local path which includes $hostbname directory
	my $hosts_ref = shift; # array-reference to host list to copy from 
	my $src_files_ref = shift; # array-refernce to file list to fetch
	my $src_path = shift; # a single src path where all files in list can be found
	my $dst_path = shift;
	if (!$dst_path) {
		$dst_path="/tmp/";
	}
	my $inv_file = build_inventory($hosts_ref);
	my @tasks;
	for my $src_file (@$src_files_ref) {
		my %task = ( "name" => "copy files from hosts", "fetch" => "flat=yes " . "src=" .
			     $src_path . "/" . $src_file . " dest=" .  $dst_path .
			     "/{{ inventory_hostname }}/" . $src_file);
		push(@tasks, \%task);
	}
	my %play = ( hosts => "all", tasks => \@tasks );;
	my @playbook = (\%play);;
	my $playbook_file = build_playbook(\@playbook);
	my $full_cmd = "ANSIBLE_CONFIG=/var/lib/pbench-agent/ansible.cfg " .
			$ansible_playbook_cmdline . " -i " .  $inv_file . " " . $playbook_file;
	print "ansible cmdline:\n$full_cmd\n";
	my $output = `$full_cmd`;
	unlink $inv_file, $playbook_file;
	return $output;
}
sub sync_dir_from_hosts { # copies files from remote hosts to a local path which includes $hostbname directory
	my $hosts_ref = shift; # array-reference to host list to copy from 
	my $src_dir = shift; # the dir to sync from on the hosts
	my $dst_dir = shift; # a single dst dir where all the remote host dirs will be sync'd to, first with a dir=hostname
	my $inv_file = build_inventory($hosts_ref);
	my @tasks;
	my %task = ( "name" => "sync dirs from hosts", "synchronize" => "mode=pull src=" . $src_dir . " dest=" . $dst_dir .
		     "/{{ inventory_hostname }}/");
	push(@tasks, \%task);
	my %play = ( hosts => "all", tasks => \@tasks );;
	my @playbook = (\%play);;
	my $playbook_file = build_playbook(\@playbook);
	my $full_cmd = "ANSIBLE_CONFIG=/var/lib/pbench-agent/ansible.cfg " .
			$ansible_playbook_cmdline . " -i " .  $inv_file . " " . $playbook_file;
	print "ansible cmdline:\n$full_cmd\n";
	my $output = `$full_cmd`;
	unlink $inv_file, $playbook_file;
	return $output;
}
sub remove_files_from_hosts { # copies files from remote hosts to a local path which includes $hostbname directory
	my $hosts_ref = shift; # array-reference to host list to copy from 
	my $src_files_ref = shift; # array-refernce to file list to fetch
	my $src_path = shift; # a single src path where all files in list can be found
	my $inv_file = build_inventory($hosts_ref);
	my @tasks;
	for my $src_file (@$src_files_ref) {
		my %task = ( "name" => "remove files from hosts", "file" => "path=" . $src_path . "/" . $src_file . " state=absent" );
		push(@tasks, \%task);
	}
	my %play = ( hosts => "all", tasks => \@tasks );;
	my @playbook = (\%play);;
	my $playbook_file = build_playbook(\@playbook);
	my $full_cmd = "ANSIBLE_CONFIG=/var/lib/pbench-agent/ansible.cfg " .
			$ansible_playbook_cmdline . " -i " .  $inv_file . " " . $playbook_file;
	print "ansible cmdline:\n$full_cmd\n";
	my $output = `$full_cmd`;
	unlink $inv_file, $playbook_file;
	return $output;
}
sub create_dir_hosts { #creates a directory on remote hosts
	my $hosts_ref = shift; # array-reference to host list to copy from 
	my $dir = shift; # the directory to create
	my $inv_file = build_inventory($hosts_ref);
	my @tasks;
	my %task = ( "name" => "create dir on hosts", "file" => "path=" . $dir . " state=directory" );
	push(@tasks, \%task);
	my %play = ( hosts => "all", tasks => \@tasks );;
	my @playbook = (\%play);;
	my $playbook_file = build_playbook(\@playbook);
	my $full_cmd = "ANSIBLE_CONFIG=/var/lib/pbench-agent/ansible.cfg " .
			$ansible_playbook_cmdline . " -i " .  $inv_file . " " . $playbook_file;
	print "ansible cmdline:\n$full_cmd\n";
	my $output = `$full_cmd`;
	unlink $inv_file, $playbook_file;
	return $output;
}
1;
