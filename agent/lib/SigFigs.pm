package SigFigs;

# Copyright (c) 1995-2015 Sullivan Beck. All rights reserved.
# This program is free software; you can redistribute it and/or modify it
# under the same terms as Perl itself.

########################################################################

require 5.004;
require Exporter;
use Carp;
use strict;
use warnings;

our (@ISA,@EXPORT,@EXPORT_OK,%EXPORT_TAGS);
use base qw(Exporter);
@EXPORT     = qw(FormatSigFigs
                 CountSigFigs
               );
@EXPORT_OK  = qw(FormatSigFigs
                 CountSigFigs
                 addSF subSF multSF divSF
                 VERSION);

%EXPORT_TAGS = ('all' => \@EXPORT_OK);

our($VERSION);
$VERSION = 1.10;

use strict;

sub addSF {
   my($n1,$n2)=@_;
   return ()     if (! (defined $n1  ||  defined $n2));
   $n1    = 0    if (! defined($n1));
   $n2    = 0    if (! defined($n2));
   $n1    = _Simplify($n1);
   $n2    = _Simplify($n2);
   return $n2    if ($n1==0);
   return $n1    if ($n2==0);

   my $m1 = _LSP($n1);
   my $m2 = _LSP($n2);
   my $m  = ($m1>$m2 ? $m1 : $m2);

   my($n) = $n1+$n2;
   my($s) = ($n<0 ? q{-} : "");
   $n     = -1*$n  if ($n<0);          # n = 1234.44           5678.99
   $n     =~ /^(\d*)/;
   my $i  = ($1);                      # i = 1234              5678
   my $l  = length($i);                # l = 4

   if ($m>0) {                         # m = 5,4,3,2,1
      if ($l >= $m+1) {                # m = 3,2,1; l-m = 1,2,3
         $n = FormatSigFigs($n,$l-$m); # n = 1000,1200,1230    6000,5700,5680
      } elsif ($l == $m) {             # m = 4
         if ($i =~ /^[5-9]/) {
            $n = 1 . "0"x$m;           # n =                   10000
         } else {
            return 0;                  # n = 0
         }
      } else {                         # m = 5
         return 0;
      }

   } elsif ($i>0) {                    # n = 1234.44           5678.99
      $n = FormatSigFigs($n,$l-$m);    # m = 0,-1,-2,...

   } else {                            # n = 0.1234    0.00123   0.00567
      $n =~ /\.(0*)(\d+)/;
      my ($z,$d) = ($1,$2);
      $m = -$m;

      if ($m > length($z)) {           # m = -1,-2,..  -3,-4,..  -3,-4,..
         $n = FormatSigFigs($n,$m-length($z));

      } elsif ($m == length($z)) {     # m =           -2        -2
         if ($d =~ /^[5-9]/) {
            $n = "0."."0"x($m-1)."1";  # n =                     0.01
         } else {
            return 0;                  # n =           0
         }

      } else {                         # m =           -1        -1
         return 0;
      }
   }

   return "$s$n";
}

sub subSF {
   my($n1,$n2)=@_;
   return ()  if (! (defined $n1  ||  defined $n2));
   $n1 = 0  if (! defined($n1));
   $n2 = 0  if (! defined($n2));

   $n2 = _Simplify($n2);
   if ($n2<0) {
      $n2 =~ s/\-//;
   } else {
      $n2 =~ s/^\+?/-/;
   }
   addSF($n1,$n2);
}

sub multSF {
   my($n1,$n2)=@_;
   return ()  if (! (defined $n1  ||  defined $n2));
   return 0   if (! defined $n1  ||  ! defined $n2  ||
                  $n1==0  ||  $n2==0);
   $n1     = _Simplify($n1);
   $n2     = _Simplify($n2);
   my($m1) = CountSigFigs($n1);
   my($m2) = CountSigFigs($n2);
   my($m)  = ($m1<$m2 ? $m1 : $m2);
   my($n)  = $n1*$n2;
   FormatSigFigs($n,$m);
}

sub divSF {
   my($n1,$n2)=@_;
   return ()  if (! (defined $n1  ||  defined $n2));
   return 0   if (! defined $n1  ||  $n1==0);
   return ()  if (! defined $n2  ||  $n2==0);
   $n1     = _Simplify($n1);
   $n2     = _Simplify($n2);

   my($m1) = CountSigFigs($n1);
   my($m2) = CountSigFigs($n2);
   my($m)  = ($m1<$m2 ? $m1 : $m2);
   my($n)  = $n1/$n2;
   FormatSigFigs($n,$m);
}

sub FormatSigFigs {
   my($N,$n) = @_;
   my($ret);
   $N        = _Simplify($N);
   return ""  if (! (defined($N)  &&  $n =~ /^\d+$/  &&  $n>0));

   $N        =~ s/^([+-]?)//;           # Remove sign
   my $s     =  $1;
   return "${s}0"   if ($N==0);

   $N        =~ s/0+$//  if ($N=~/\./); # Remove all trailing zeros after decimal
   $N        = "0$N"  if ($N=~ /^\./);  # Turn .2 into 0.2

   my($l,$l1,$l2,$m)=();

   $m    = CountSigFigs($N);

   # If the number has the right number of sigfigs already, we'll return
   # it with one minor modification:
   #     turn 24 (2) into 24.
   # but
   #     don't turn 2400 (2) into 2400.

   if ($m==$n) {
      $N  = "$N."  if (length($N)==$n);
      return "$s$N";
   }

   # If the number has too few sigfigs, we need to pad it with some zeroes.

   if ($m<$n) {
      if ($N=~ /\./) {
         # 0.012 (4) => 0.01200
         # 1.12 (4)  => 1.120
         return "$s$N" . "0"x($n-$m);
      }

      # 120 (4)   => 120.0
      # 1200 (4)  => 1200.
      # 12000 (4) => 12000

      $l = length($N);
      return "$s$N"  if ($l>$n);
      return "$s$N." . "0"x($n-$l);
   }

   # Anything else has too many sigfigs.
   #
   # Handle:
   #      0.0123 (2) => 0.012

   $N = "$N."  if ($N !~ /\./);            # 123.
   if ($N=~ /^0\.(0*)(\d*)$/) {            # 0.0001234 (2)
      ($l1,$l2) = (length($1),length($2)); # (l1,l2) = (3,4)
      $N        =~ s/5$/6/;
      $l        = $l1+$n;                  # 5
      $ret      = sprintf("%.${l}f",$N);   # 0.00012
      $m        = CountSigFigs($ret);
      return "$s$ret"  if ($n==$m);

      # special cases 0.099 (1) -> 0.1
      #               0.99  (1) -> 1.

      $l--;
      $ret      = sprintf("%.${l}f",$N);
      $m        = CountSigFigs($ret);
      $ret      = "$ret."  if ($l==0);
      return "$s$ret";
   }

   # Handle:
   #     123.4567 (3) => 123.
   #     123.4567 (4) => 123.5
   # Also handle part of:
   #     1234.567 (3) => 1235 (3)

   $N=~ /^(\d+)\.(\d*)/;                # 123.4567
   my($n1,$n2) = ($1,$2);
   ($l1,$l2)=(length($n1),length($n2)); # (l1,l2) = (3,4)

   # Keep some decimal points (or exactly 0)

   if ($n>=$l1) {
      $l   = $n-$l1;         # l = number of decimal points to keep
      $N   =~ s/5$/6/;       # 4.95 rounds down... make it go up
      $ret = sprintf("%.${l}f",$N);
      $m   = CountSigFigs($ret);
      if ($m==$n) {
         $ret="$ret."  if ($l==0 && $m==length($ret));
         return "$s$ret";
      }

      # special case 9.99 (2) -> 10.
      #              9.99 (1) -> 10

      $l--;
      if ($l>=0) {
         $ret = sprintf("%.${l}f",$N);
         $ret = "$ret."  if ($l==0);
         return "$s$ret";
      }
      return "$s$ret";
   }

   # Otherwise, we're removing all decimal points (and it needs to be
   # truncated even further).  Truncate (not
   # round) to an integer and pass through.

   $N = $n1;

   # Handle integers (the only case here is that we want fewer sigfigs
   # than the lenght of the number.
   #    123 (2) => 120

   #                                        123     9900 (3)  9900 (2)   9900 (1)
   $l        = length($N);                # 3       4         4          4
   $N        =~ s/0*$//;                  # 123     99        99         99
   $N        =~ s/5$/6/;
   $m        = sprintf("%.${n}f",".$N");  # .123    .990     .99         1.0
   if ($m>=1) {
      $n--;
      $l++;
      $m     = sprintf("%.${n}f",".$N");  # .123    .990     .99         1.
   }
   $m        =~ s/^0//;
   $m        =~ s/\.//;
   $N        = $m . "0"x($l-length($m));
   return "$s$N";
}

sub CountSigFigs {
   my($N) = @_;
   $N     = _Simplify($N);
   return ()  if (! defined($N));
   return 0   if ($N==0);

   $N     =~ s/^[+-]//;
   if ($N=~ /^\d+$/) {
      $N =~ s/0*$//;
      return length($N);
   } elsif ($N=~ /^\.0*(\d+)$/) {
      return length($1);
   } else {
      return length($N)-1;
   }
}

########################################################################
# NOT FOR EXPORT
#
# These are exported above only for debug purposes.  They are not
# for general use.  They are not guaranteed to remain backward
# compatible (or even to exist at all) in future versions.
########################################################################

# This returns the power of the least sigificant digit.
#
sub _LSP {
   my($n) = @_;
   $n =~ s/\-//;
   if ($n =~ /(.*)\.(.+)/) {
      return -length($2);
   } elsif ($n =~ /\.$/) {
      return 0;
   } else {
      return length($n) - CountSigFigs($n);
   }
}

# This prepares a number by converting it to it's simplest correct
# form.
#
# Strip out spaces and leading zeroes before a decimal point.
#
sub _Simplify {
   my($n)    = @_;
   return undef  if (! defined $n);
   if ($n =~ /^\s*([+-]?)\s*0*(\.\d+)\s*$/  ||
       $n =~ /^\s*([+-]?)\s*0*(\d+\.?\d*)\s*$/) {
      my($s,$num)=($1,$2);
      $num = 0  if ($num==0);
      return "$s$num";
   }
   return undef;
}

1;
# Local Variables:
# mode: cperl
# indent-tabs-mode: nil
# cperl-indent-level: 3
# cperl-continued-statement-offset: 2
# cperl-continued-brace-offset: 0
# cperl-brace-offset: 0
# cperl-brace-imaginary-offset: 0
# cperl-label-offset: 0
# End:
