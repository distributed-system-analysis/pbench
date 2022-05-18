// Copyright (c) 2019, NVIDIA CORPORATION. All rights reserved.
//
// Redistribution and use in source and binary forms, with or without
// modification, are permitted provided that the following conditions
// are met:
//  * Redistributions of source code must retain the above copyright
//    notice, this list of conditions and the following disclaimer.
//  * Redistributions in binary form must reproduce the above copyright
//    notice, this list of conditions and the following disclaimer in the
//    documentation and/or other materials provided with the distribution.
//  * Neither the name of NVIDIA CORPORATION nor the names of its
//    contributors may be used to endorse or promote products derived
//    from this software without specific prior written permission.
//
// THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS ``AS IS'' AND ANY
// EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
// IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
// PURPOSE ARE DISCLAIMED.  IN NO EVENT SHALL THE COPYRIGHT OWNER OR
// CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
// EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
// PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
// PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY
// OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
// (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
// OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#pragma once

#include <time.h>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <random>

#include <sys/stat.h>
#include "src/clients/c++/library/request_grpc.h"
#include "src/clients/c++/library/request_http.h"
#include "src/core/constants.h"

namespace ni = nvidia::inferenceserver;
namespace nic = nvidia::inferenceserver::client;

namespace perfclient {

using TimestampVector =
    std::vector<std::tuple<struct timespec, struct timespec, uint32_t>>;

// Will use the characters specified here to construct random strings
std::string const character_set =
    "abcdefghijklmnaoqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890 .?!";

// A boolean flag to mark an interrupt and commencement of early exit
extern volatile bool early_exit;


#define RETURN_IF_ERROR(S)            \
  do {                                \
    const nic::Error& status__ = (S); \
    if (!status__.IsOk()) {           \
      return status__;                \
    }                                 \
  } while (false)

#define FAIL_IF_ERR(X, MSG)                                        \
  {                                                                \
    nic::Error err = (X);                                          \
    if (!err.IsOk()) {                                             \
      std::cerr << "error: " << (MSG) << ": " << err << std::endl; \
      exit(1);                                                     \
    }                                                              \
  }

enum ProtocolType { HTTP = 0, GRPC = 1, UNKNOWN = 2 };

// Parse the communication protocol type
ProtocolType ParseProtocol(const std::string& str);

// Reads the data from file specified by path into vector of characters
// \param path The complete path to the file to be read
// \param contents The character vector that will contain the data read
// \return error status. Returns Non-Ok if an error is encountered during
//  read operation.
nic::Error ReadFile(const std::string& path, std::vector<char>* contents);

// Reads the string from file specified by path into vector of strings
// \param path The complete path to the file to be read
// \param contents The string vector that will contain the data read
// \return error status. Returns Non-Ok if an error is encountered during
//  read operation.
nic::Error ReadTextFile(
    const std::string& path, std::vector<std::string>* contents);

// To check whether the path points to a valid system directory
bool IsDirectory(const std::string& path);

// Generates a random string of specified length using characters specified in
// character_set.
std::string GetRandomString(const int string_length);

}  // namespace perfclient
