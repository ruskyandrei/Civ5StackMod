[CmdletBinding()]
param([Parameter(Mandatory=$true)][ValidateRange(1,2147483647)][int]$GameProcessId,[Parameter(Mandatory=$true)][long]$ExpectedStartTicks,[Parameter(Mandatory=$true)][string]$RunDirectory,[string]$CompletionSignalPath,[ValidateRange(1,180)][int]$MaximumSeconds=180,[ValidateRange(1,10)][int]$SampleSeconds=2,[switch]$Watch,[switch]$StopOnLimit,[switch]$ValidateOnly)
$ErrorActionPreference='Stop'
function Resolve-CivMemoryRunDirectory([string]$Path) {
 $root=[IO.Path]::GetFullPath('E:\Projects\Civ5StackMod\work\test-runs').TrimEnd('\')+'\'
 if (-not [IO.Path]::IsPathRooted($Path)) { throw 'RunDirectory must be absolute.' }
 $p=[IO.Path]::GetFullPath($Path).TrimEnd('\')
 if (-not $p.StartsWith($root,[StringComparison]::OrdinalIgnoreCase)) { throw 'RunDirectory must be below project work\test-runs.' };return $p
}
function Resolve-CivMemorySignal([string]$Path) {
 if ([string]::IsNullOrWhiteSpace($Path)) { return $null }
 $root=[IO.Path]::GetFullPath('C:\Users\rusit\Documents\Codex\Civ5StackMod-watchdog')
 if (-not [IO.Path]::IsPathRooted($Path)) { throw 'Signal path must be absolute.' }
 $p=[IO.Path]::GetFullPath($Path)
 if (-not [string]::Equals([IO.Path]::GetDirectoryName($p),$root,[StringComparison]::OrdinalIgnoreCase) -or -not $p.EndsWith('.signal',[StringComparison]::OrdinalIgnoreCase)) { throw 'Signal must be a direct .signal file in the existing watchdog folder.' };return $p
}
function Get-CivMemoryLimitReason($Sample,[double]$ElapsedSeconds,[int]$MaximumSeconds) {
 if ([long]$Sample.PrivateBytes -ge [long](3.1GB)) { return 'private_bytes_3.1GiB' }
 if (([long]$Sample.CommittedBytes+[long]$Sample.ReservedBytes) -ge [long](3.5GB)) { return 'commit_plus_reserve_3.5GiB' }
 if ([long]$Sample.FreeBytes -lt 256MB) { return 'free_below_256MiB' }
 if ([long]$Sample.LargestFreeBytes -lt 16MB) { return 'largest_free_below_16MiB' }
 if ($ElapsedSeconds -ge $MaximumSeconds) { return 'maximum_duration' };return $null
}
$nativeSource=@"
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;
using System.Text;
namespace CivMemoryWatch {
 public sealed class Snapshot { public int Pid,Regions; public long StartTicks,PrivateBytes,WorkingSetBytes,CommittedBytes,ReservedBytes,FreeBytes,LargestFreeBytes,Cpu100ns; public string Executable,Utc; }
 public static class Native {
  const string Exe=@"E:\SteamLibrary\steamapps\common\Sid Meier's Civilization V\CivilizationV_DX11.exe";
  [StructLayout(LayoutKind.Sequential)] public struct MBI64 {public ulong BaseAddress,AllocationBase;public uint AllocationProtect,Alignment1;public ulong RegionSize;public uint State,Protect,Type,Alignment2;}
  [StructLayout(LayoutKind.Sequential)] struct Counters {public uint cb,PageFaultCount;public UIntPtr PeakWorkingSetSize,WorkingSetSize,QuotaPeakPagedPoolUsage,QuotaPagedPoolUsage,QuotaPeakNonPagedPoolUsage,QuotaNonPagedPoolUsage,PagefileUsage,PeakPagefileUsage,PrivateUsage;}
  [DllImport("kernel32.dll",SetLastError=true)] static extern IntPtr OpenProcess(uint access,bool inherit,int pid);
  [DllImport("kernel32.dll",SetLastError=true)] static extern bool CloseHandle(IntPtr h);
  [DllImport("kernel32.dll",SetLastError=true,CharSet=CharSet.Unicode)] static extern bool QueryFullProcessImageName(IntPtr h,uint flags,StringBuilder name,ref int size);
  [DllImport("kernel32.dll",SetLastError=true)] static extern bool GetProcessTimes(IntPtr h,out long creation,out long exit,out long kernel,out long user);
  [DllImport("kernel32.dll",SetLastError=true)] static extern bool IsWow64Process(IntPtr h,out bool wow);
  [DllImport("kernel32.dll",SetLastError=true)] static extern UIntPtr VirtualQueryEx(IntPtr h,IntPtr address,out MBI64 info,UIntPtr size);
  [DllImport("psapi.dll",SetLastError=true)] static extern bool GetProcessMemoryInfo(IntPtr h,ref Counters c,uint size);
  [DllImport("kernel32.dll",SetLastError=true)] static extern bool TerminateProcess(IntPtr h,uint code);
  static void Check(bool ok,string action){if(!ok)throw new Win32Exception(Marshal.GetLastWin32Error(),action);}
  static Snapshot Verify(IntPtr h,int pid,long ticks){long create,exit,kernel,user;Check(GetProcessTimes(h,out create,out exit,out kernel,out user),"GetProcessTimes");int n=32768;StringBuilder p=new StringBuilder(n);Check(QueryFullProcessImageName(h,0,p,ref n),"QueryFullProcessImageName");long actual=DateTime.FromFileTimeUtc(create).Ticks;
   if(actual!=ticks||!String.Equals(p.ToString(),Exe,StringComparison.OrdinalIgnoreCase)||exit!=0)throw new InvalidOperationException("Exact live PID creation time and DX11 executable mismatch; no action.");bool wow;Check(IsWow64Process(h,out wow),"IsWow64Process");if(!wow)throw new InvalidOperationException("Expected32-bit game on64-bit host.");return new Snapshot{Pid=pid,StartTicks=actual,Executable=p.ToString(),Cpu100ns=kernel+user,Utc=DateTime.UtcNow.ToString("o")};}
  static IntPtr Open(int pid,uint access){if(IntPtr.Size!=8)throw new InvalidOperationException("Use64-bit PowerShell.");IntPtr h=OpenProcess(access,false,pid);if(h==IntPtr.Zero)throw new Win32Exception(Marshal.GetLastWin32Error(),"OpenProcess");return h;}
  public static Snapshot Read(int pid,long ticks,bool identityOnly){IntPtr h=Open(pid,0x0410);try{Snapshot s=Verify(h,pid,ticks);if(identityOnly)return s;Counters c=new Counters();c.cb=(uint)Marshal.SizeOf(typeof(Counters));Check(GetProcessMemoryInfo(h,ref c,c.cb),"GetProcessMemoryInfo");s.PrivateBytes=(long)c.PrivateUsage.ToUInt64();s.WorkingSetBytes=(long)c.WorkingSetSize.ToUInt64();
   // Match crash markers:0x10000 through0xFFFEFFFF inclusive.
   const ulong upper=0xFFFF0000UL;ulong address=0x10000;
   while(address<upper){MBI64 m;UIntPtr got=VirtualQueryEx(h,new IntPtr((long)address),out m,new UIntPtr((uint)Marshal.SizeOf(typeof(MBI64))));if(got.ToUInt64()!=48||m.RegionSize==0)throw new Win32Exception(Marshal.GetLastWin32Error(),"VirtualQueryEx incomplete; no partial totals");ulong next=m.BaseAddress+m.RegionSize;if(next<=address)throw new InvalidOperationException("Nonprogressing memory region.");ulong end=Math.Min(next,upper);long length=(long)(end-address);if(m.State==0x1000)s.CommittedBytes+=length;else if(m.State==0x2000)s.ReservedBytes+=length;else if(m.State==0x10000){s.FreeBytes+=length;s.LargestFreeBytes=Math.Max(s.LargestFreeBytes,length);}else throw new InvalidOperationException("Unknown memory state.");++s.Regions;address=end;}Verify(h,pid,ticks);return s;}finally{CloseHandle(h);}}
  // Stop owns a verified handle, preventing a PID-reuse gap between checking and termination.
  public static void StopExact(int pid,long ticks){IntPtr h=Open(pid,0x0411);try{Verify(h,pid,ticks);Check(TerminateProcess(h,1),"TerminateProcess exact test");}finally{CloseHandle(h);}}
 }
}
"@
if ([IntPtr]::Size -ne 8) { throw 'Use64-bit PowerShell for48-byte VirtualQueryEx layout.' }
$runRoot=Resolve-CivMemoryRunDirectory $RunDirectory
$signal=Resolve-CivMemorySignal $CompletionSignalPath
if ($signal -and [IO.File]::Exists($signal)) { throw 'Signal already exists; choose a fresh signal.' }
if (-not ('CivMemoryWatch.Native' -as [type])) { Add-Type -TypeDefinition $nativeSource }
if ($ValidateOnly) { [CivMemoryWatch.Native]::Read($GameProcessId,$ExpectedStartTicks,$true) | ConvertTo-Json -Compress;return }
$walk=$runRoot
while ($walk -and $walk.Length -gt 3) {if (Test-Path -LiteralPath $walk) {if ((Get-Item -LiteralPath $walk).Attributes -band [IO.FileAttributes]::ReparsePoint) {throw 'RunDirectory cannot traverse reparse points.'}};$walk=[IO.Path]::GetDirectoryName($walk)}
[void][CivMemoryWatch.Native]::Read($GameProcessId,$ExpectedStartTicks,$true)
[void][IO.Directory]::CreateDirectory($runRoot)
$log=Join-Path $runRoot ('memory-watch-'+[DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss-fff')+'.jsonl')
$timer=[Diagnostics.Stopwatch]::StartNew()
function Write-MemoryEvent($Event) {$line=$Event|ConvertTo-Json -Compress -Depth 5;[IO.File]::AppendAllText($log,$line+[Environment]::NewLine,[Text.Encoding]::UTF8);Write-Output $line}
Write-MemoryEvent @{event='armed';utc=[DateTime]::UtcNow.ToString('o');pid=$GameProcessId;startTicks=$ExpectedStartTicks;watch=[bool]$Watch;stopOnLimit=[bool]$StopOnLimit;maximumSeconds=$MaximumSeconds;sampleSeconds=$SampleSeconds;signal=$signal}
while ($true) {
 if ($signal -and [IO.File]::Exists($signal)) {Write-MemoryEvent @{event='completed';reason='manual_signal';elapsed=$timer.Elapsed.TotalSeconds};break}
 try {$sample=[CivMemoryWatch.Native]::Read($GameProcessId,$ExpectedStartTicks,$false)}catch{Write-MemoryEvent @{event='sampling_stopped';reason=$_.Exception.Message;elapsed=$timer.Elapsed.TotalSeconds};break}
 $elapsed=$timer.Elapsed.TotalSeconds;$reason=Get-CivMemoryLimitReason $sample $elapsed $MaximumSeconds
 Write-MemoryEvent @{event='sample';elapsed=$elapsed;limit=$reason;sample=$sample}
 if ($reason) {
  if ($signal -and [IO.File]::Exists($signal)) {Write-MemoryEvent @{event='completed';reason='manual_signal_before_stop';elapsed=$timer.Elapsed.TotalSeconds};break}
  if ($StopOnLimit) {try{[CivMemoryWatch.Native]::StopExact($GameProcessId,$ExpectedStartTicks);Write-MemoryEvent @{event='stopped_exact_test';reason=$reason;elapsed=$timer.Elapsed.TotalSeconds}}catch{Write-MemoryEvent @{event='stop_refused_or_failed';reason=$_.Exception.Message;elapsed=$timer.Elapsed.TotalSeconds}}}else{Write-MemoryEvent @{event='limit_observed_no_stop';reason=$reason;elapsed=$elapsed}};break
 }
 if (-not $Watch) {break}
 Start-Sleep -Milliseconds ([int][Math]::Min($SampleSeconds*1000,[Math]::Max(1,($MaximumSeconds-$timer.Elapsed.TotalSeconds)*1000)))
}
